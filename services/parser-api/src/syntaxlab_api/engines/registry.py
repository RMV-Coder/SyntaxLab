"""Engine discovery.

Engines are resolved by name from the ``syntaxlab.engines`` entry-point group, so any installed
package can contribute one. A fully qualified ``"package.module:ClassName"`` reference is also
accepted, which is convenient for local or experimental engines.
"""

from __future__ import annotations

import importlib
from importlib.metadata import entry_points

from syntaxlab_api.engines.base import Engine, EngineConfigError

ENTRY_POINT_GROUP = "syntaxlab.engines"


def available_engines() -> dict[str, str]:
    """Installed engine names mapped to their import target (without importing them)."""
    return {ep.name: ep.value for ep in entry_points(group=ENTRY_POINT_GROUP)}


def resolve_engine(reference: str) -> type[Engine]:
    """Return the engine class for an entry-point name or a ``module:Class`` reference."""
    if ":" in reference:
        module_name, _, attr = reference.partition(":")
        try:
            obj = getattr(importlib.import_module(module_name), attr)
        except (ImportError, AttributeError) as exc:
            raise EngineConfigError(f"cannot import engine {reference!r}: {exc}") from exc
    else:
        matches = [ep for ep in entry_points(group=ENTRY_POINT_GROUP) if ep.name == reference]
        if not matches:
            known = ", ".join(sorted(available_engines())) or "none"
            raise EngineConfigError(
                f"unknown engine {reference!r}; installed engines: {known}. "
                "Install the package that provides it, or use a 'module:Class' reference."
            )
        try:
            obj = matches[0].load()
        except ImportError as exc:
            raise EngineConfigError(
                f"engine {reference!r} is registered but its dependencies are missing: {exc}"
            ) from exc

    if not (isinstance(obj, type) and issubclass(obj, Engine)):
        raise EngineConfigError(f"{reference!r} does not refer to an Engine subclass")
    return obj
