"""Tests for plugin discovery and loading logic."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from kennabot.plugins.base import BasePlugin


class _FakePlugin(BasePlugin):
    """Minimal BasePlugin implementation used for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return "fake"

    @property
    def table_prefix(self) -> str:
        return f"plugin_{self._name}_"

    async def register(self, app, session_factory, settings) -> None:
        pass


def _make_cls(plugin_name: str, qualname_suffix: str = "") -> type[BasePlugin]:
    """Return a new BasePlugin subclass whose ``name`` property returns *plugin_name*."""

    class _Cls(_FakePlugin):
        def __init__(self) -> None:
            super().__init__(plugin_name)

    suffix = qualname_suffix or plugin_name
    _Cls.__name__ = f"Plugin_{suffix}"
    _Cls.__qualname__ = f"Plugin_{suffix}"
    _Cls.__module__ = "tests.fake"
    return _Cls


def _patch_discovery(monkeypatch, plugin_classes: list[type[BasePlugin]]) -> None:
    """Patch the three internal hooks discover_plugins() uses so it returns *plugin_classes*."""
    # Build one fake module per class, each claiming to be a distinct plugin package.
    fake_modules: dict[str, MagicMock] = {}
    items: list[MagicMock] = []

    for i, _cls in enumerate(plugin_classes):
        pkg_name = f"fake_pkg_{i}"
        module_name = f"kennabot.plugins.{pkg_name}.plugin"

        fake_mod = MagicMock()
        fake_mod.__name__ = module_name
        fake_modules[module_name] = fake_mod

        item = MagicMock()
        item.ispkg = True
        item.name = pkg_name
        items.append(item)

    def fake_iter_modules(_dirs):
        return items

    def fake_import(module_name):
        return fake_modules.get(module_name, MagicMock())

    def fake_getmembers(module, predicate):
        for mod_name, mod in fake_modules.items():
            if module is mod:
                idx = int(mod_name.split("fake_pkg_")[1].split(".")[0])
                return [(f"Cls{idx}", plugin_classes[idx])]
        return []

    monkeypatch.setattr("kennabot.plugins.pkgutil.iter_modules", fake_iter_modules)
    monkeypatch.setattr("kennabot.plugins.importlib.import_module", fake_import)
    monkeypatch.setattr("kennabot.plugins.inspect.getmembers", fake_getmembers)


class TestDiscoverPluginsDuplicateNames:
    """discover_plugins() must refuse to return a list with duplicate names."""

    def test_unique_names_accepted(self, monkeypatch):
        """Two plugins with different names should be discovered without error."""
        import kennabot.plugins as loader

        cls_a = _make_cls("alpha")
        cls_b = _make_cls("beta")
        _patch_discovery(monkeypatch, [cls_a, cls_b])

        result = loader.discover_plugins()
        assert len(result) == 2
        names = {cls().name for cls in result}
        assert names == {"alpha", "beta"}

    def test_duplicate_names_raise_system_exit(self, monkeypatch, caplog):
        """Two plugins sharing the same name must cause SystemExit with a clear message."""
        import kennabot.plugins as loader

        cls_a = _make_cls("plusplus")
        cls_b = _make_cls("plusplus", qualname_suffix="plusplus_duplicate")
        _patch_discovery(monkeypatch, [cls_a, cls_b])

        with (
            caplog.at_level(logging.CRITICAL, logger="kennabot.plugins"),
            pytest.raises(SystemExit) as exc_info,
        ):
            loader.discover_plugins()

        error_message = str(exc_info.value)
        assert "plusplus" in error_message
        assert "Duplicate plugin names" in error_message
        assert "cannot start" in error_message
