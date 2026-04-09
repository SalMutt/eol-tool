"""Auto-discovery registry for EOL checkers."""

import importlib
import pkgutil

from . import checkers as checkers_pkg
from .checker import BaseChecker

_registry: dict[str, list[type[BaseChecker]]] = {}
_discovered = False

# Route models from one manufacturer to another manufacturer's checkers.
# Key: alias (lowercase), Value: target manufacturer (lowercase).
_MANUFACTURER_ALIASES: dict[str, str] = {
    "crucial": "micron",
}


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
    key = manufacturer.lower()
    entries = _registry.get(key)
    if entries:
        return entries[0]
    alias_key = _MANUFACTURER_ALIASES.get(key)
    if alias_key:
        entries = _registry.get(alias_key)
        return entries[0] if entries else None
    return None


def get_checkers(manufacturer: str) -> list[type[BaseChecker]]:
    """Get all checker classes registered for a manufacturer."""
    if not _discovered:
        _discover_checkers()
    key = manufacturer.lower()
    result = list(_registry.get(key, []))
    alias_key = _MANUFACTURER_ALIASES.get(key)
    if alias_key and alias_key in _registry:
        for checker in _registry[alias_key]:
            if checker not in result:
                result.append(checker)
    return result


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
