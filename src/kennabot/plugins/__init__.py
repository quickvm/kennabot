"""Plugin auto-discovery and loading for KennaBot.

Scans subdirectories of the plugins package for modules containing a
class that inherits from BasePlugin, then calls register() on each.

Plugins can be restricted via the ``KENNABOT_ENABLED_PLUGINS`` setting
(a list of plugin names).  When that list is empty every discovered
plugin is loaded (the default).
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from kennabot.plugins.base import BasePlugin, validate_table_prefix

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp

    from kennabot.config import Settings

logger = logging.getLogger(__name__)


def discover_plugins() -> list[type[BasePlugin]]:
    """Scan the plugins directory for BasePlugin subclasses.

    Looks for packages under kennabot/plugins/ that contain a plugin.py
    module with a class inheriting from BasePlugin.

    Raises:
        SystemExit: If two or more plugins declare the same ``name``.  A
            duplicate name means the same plugin is registered twice (e.g.
            installed both as a package and as a local directory), which would
            cause silent data or routing conflicts.  KennaBot refuses to start
            rather than silently misbehave.
    """
    plugins: list[type[BasePlugin]] = []
    plugins_dir = Path(__file__).parent

    for item in pkgutil.iter_modules([str(plugins_dir)]):
        if not item.ispkg:
            continue

        module_name = f"kennabot.plugins.{item.name}.plugin"
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            logger.warning("Failed to import plugin %s: %s", item.name, exc)
            continue

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                plugins.append(obj)
                logger.debug("Discovered plugin class: %s.%s", module_name, _name)

    # Check for duplicate plugin names and refuse to continue if any are found.
    seen: dict[str, str] = {}  # name -> first class qualified name
    duplicates: list[str] = []
    for cls in plugins:
        plugin_name = cls().name
        qualified = f"{cls.__module__}.{cls.__qualname__}"
        if plugin_name in seen:
            duplicates.append(
                f"  '{plugin_name}' registered by both {seen[plugin_name]} and {qualified}"
            )
        else:
            seen[plugin_name] = qualified

    if duplicates:
        message = (
            "Duplicate plugin names detected — KennaBot cannot start:\n"
            + "\n".join(duplicates)
            + "\nEach plugin must have a unique name.  "
            "Remove or rename the conflicting plugin."
        )
        logger.critical(message)
        raise SystemExit(message)

    return plugins


def get_enabled_plugin_names(settings: Settings) -> list[str]:
    """Return the list of plugin names that should be active.

    If ``settings.enabled_plugins`` is non-empty only those names are
    returned (in the order declared).  Otherwise every discovered plugin
    name is returned.
    """
    if settings.enabled_plugins:
        return list(settings.enabled_plugins)
    # Fall back to every discovered plugin
    return [cls().name for cls in discover_plugins()]


def _import_plugin_models(plugin_name: str) -> bool:
    """Import a plugin's models module (if it exists) to register SQLModel metadata.

    Returns True if the models module was found and imported.
    """
    models_module_name = f"kennabot.plugins.{plugin_name}.models"
    try:
        importlib.import_module(models_module_name)
        logger.debug("Imported models for plugin '%s'", plugin_name)
        return True
    except ImportError:
        return False


async def load_plugins(app: AsyncApp, settings: Settings) -> list[BasePlugin]:
    """Discover, instantiate, and register all enabled plugins.

    Only plugins whose ``name`` appears in ``settings.enabled_plugins`` are
    loaded.  When that list is empty all discovered plugins are loaded.

    For each plugin:
    1. Import the plugin's ``models`` module (if present) to register tables
       with SQLModel metadata.
    2. Validate that all table names start with the plugin's declared
       ``table_prefix``.  Raises ``ValueError`` on mismatch — the plugin is
       skipped with an error log.
    3. Call ``register()`` to attach Slack event listeners and commands.

    Args:
        app: The Slack Bolt AsyncApp.
        settings: Application configuration.

    Returns:
        List of registered plugin instances.
    """
    from kennabot.database import get_session_factory

    session_factory = get_session_factory()
    plugin_classes = discover_plugins()

    # Build an allow-set; empty means "all"
    enabled: set[str] = set(settings.enabled_plugins) if settings.enabled_plugins else set()

    registered: list[BasePlugin] = []

    for plugin_cls in plugin_classes:
        try:
            plugin = plugin_cls()

            # Skip plugins that are not in the enabled list (when a list is set)
            if enabled and plugin.name not in enabled:
                logger.debug("Skipping plugin '%s' (not in enabled_plugins)", plugin.name)
                continue

            # Import models module so SQLModel.metadata is populated
            has_models = _import_plugin_models(plugin.name)

            # Hard validate that all table names honour the prefix convention
            validate_table_prefix(plugin)

            if has_models:
                logger.debug(
                    "Plugin '%s' models validated with prefix '%s'",
                    plugin.name,
                    plugin.table_prefix,
                )

            await plugin.register(app, session_factory, settings)
            registered.append(plugin)
            logger.info("Loaded plugin: %s — %s", plugin.name, plugin.description)
        except ValueError:
            logger.exception(
                "Plugin '%s' failed table prefix validation — not loaded",
                plugin_cls.__name__,
            )
        except Exception:
            logger.exception("Failed to load plugin: %s", plugin_cls.__name__)

    logger.info("Loaded %d plugin(s)", len(registered))
    return registered
