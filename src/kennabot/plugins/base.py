"""Base plugin interface for KennaBot."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from slack_bolt.async_app import AsyncApp
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from kennabot.config import Settings


class BasePlugin(ABC):
    """Abstract base class for KennaBot plugins.

    To create a new plugin:
    1. Create a directory under src/kennabot/plugins/ (e.g. plugins/myplugin/)
    2. Add a plugin.py with a class that inherits from BasePlugin
    3. Implement the ``name``, ``description``, and ``table_prefix`` properties
    4. If the plugin uses database tables, create a ``models.py`` in the plugin
       directory.  Every ``__tablename__`` in that module **must** start with
       the value returned by ``table_prefix`` (e.g. ``"plugin_myplugin_"``).
       This prefix is enforced at load time by :func:`validate_table_prefix`.
    5. Implement the ``register`` method to attach Slack event listeners
    6. Optionally implement ``register_cli`` to add CLI management commands

    The plugin loader will automatically discover and register your plugin.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for the plugin (e.g. 'plusplus')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the plugin does."""
        ...

    @property
    @abstractmethod
    def table_prefix(self) -> str:
        """Required table name prefix for all database tables owned by this plugin.

        Must follow the pattern ``plugin_<name>_`` (e.g. ``"plugin_plusplus_"``).
        Every ``__tablename__`` defined in the plugin's ``models.py`` must start
        with this prefix.  This is validated at plugin load time.
        """
        ...

    @abstractmethod
    async def register(
        self,
        app: AsyncApp,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        """Register Slack event listeners, commands, and other handlers.

        Called once at startup by the plugin loader.

        Args:
            app: The Slack Bolt AsyncApp to register listeners on.
            session_factory: Async SQLAlchemy session factory for database access.
            settings: Application settings.
        """
        ...

    def register_cli(self, parent_app: Any) -> None:  # noqa: B027
        """Register CLI subcommands under ``kennabot <plugin-name>``.

        Override this in your plugin to add management commands.  The default
        implementation is a no-op — plugins without CLI needs can ignore this.

        Args:
            parent_app: The root Typer application. Use
                ``parent_app.add_typer(your_sub_app, name=self.name)``
                to attach your command group.
        """


def validate_table_prefix(plugin: BasePlugin) -> None:
    """Validate that all tables in the plugin's models module use the required prefix.

    Imports ``kennabot.plugins.<name>.models`` (if it exists) and checks that
    every SQLModel table class has a ``__tablename__`` starting with
    :attr:`BasePlugin.table_prefix`.

    Raises:
        ValueError: If any table name does not start with the declared prefix.
    """
    from sqlmodel import SQLModel

    plugin_module_name = f"kennabot.plugins.{plugin.name}.models"
    try:
        models_module = importlib.import_module(plugin_module_name)
    except ImportError:
        # Plugin has no models module — nothing to validate.
        return

    prefix = plugin.table_prefix
    violations: list[str] = []

    for attr_name in dir(models_module):
        obj = getattr(models_module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, SQLModel)
            and obj is not SQLModel
            and getattr(obj, "__tablename__", None) is not None
        ):
            tablename: str = obj.__tablename__
            if not tablename.startswith(prefix):
                violations.append(f"  {obj.__name__}.__tablename__ = {tablename!r}")

    if violations:
        raise ValueError(
            f"Plugin '{plugin.name}' declares table_prefix={prefix!r} but the "
            f"following tables do not use that prefix:\n"
            + "\n".join(violations)
            + f"\nAll tables must start with {prefix!r}."
        )
