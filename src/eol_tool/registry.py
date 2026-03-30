"""Auto-discovery registry for EOL checkers."""

import importlib
import pkgutil

from . import checkers as checkers_pkg
from .checker import BaseChecker

_registry: dict[str, list[type[BaseChecker]]] = {}
_discovered = False


def _discover_checkers() -> None:
    """Scan the checkers package for BaseChecker subclasses."""
    global _discovered
    for module_info in pkgutil.iter_modules(checkers_pkg.__path__):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f".checkers.{module_info.name}", package="eol_tool")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseChecker)
                and attr is not BaseChecker
                and hasattr(attr, "manufacturer_name")
            ):
                key = attr.manufacturer_name.lower()
                if key not in _registry:
                    _registry[key] = []
                if attr not in _registry[key]:
                    _registry[key].append(attr)
    _discovered = True


def get_checker(manufacturer: str) -> type[BaseChecker] | None:
    """Get the first checker class by manufacturer name (backward compat)."""
    if not _discovered:
        _discover_checkers()
    entries = _registry.get(manufacturer.lower())
    return entries[0] if entries else None


def get_checkers(manufacturer: str) -> list[type[BaseChecker]]:
    """Get all checker classes registered for a manufacturer."""
    if not _discovered:
        _discover_checkers()
    return list(_registry.get(manufacturer.lower(), []))


def list_checkers() -> dict[str, type[BaseChecker]]:
    """List registered checkers (first per manufacturer, backward compat)."""
    if not _discovered:
        _discover_checkers()
    return {k: v[0] for k, v in _registry.items() if v}


def list_all_checkers() -> dict[str, list[type[BaseChecker]]]:
    """List all registered checkers grouped by manufacturer."""
    if not _discovered:
        _discover_checkers()
    return {k: list(v) for k, v in _registry.items()}
