"""Explicit, versioned discovery of optional observation-source plugins."""

from __future__ import annotations

from importlib.metadata import entry_points
import inspect
import re
from typing import Any, Callable, Protocol, runtime_checkable

from .adapters import ObservationSource


PLUGIN_API_VERSION = "1"
ENTRY_POINT_GROUP = "timoshenko.plugins"


class PluginError(RuntimeError):
    """Base exception for invalid or incompatible engine plugins."""


class PluginCompatibilityError(PluginError):
    """Raised when a plugin targets a different plugin API version."""


class PluginLoadError(PluginError):
    """Raised when installed plugin code cannot be loaded or registered."""


@runtime_checkable
class EnginePlugin(Protocol):
    name: str
    api_version: str

    def register(self, registry: "PluginContributions") -> None: ...


class PluginContributions:
    """A staging area; contributions become visible only after registration succeeds."""

    def __init__(self) -> None:
        self._source_factories: dict[str, Callable[..., ObservationSource]] = {}

    def register_source(self, name: str, factory: Callable[..., ObservationSource]) -> None:
        key = _normalize_name(name, "source")
        if not callable(factory):
            raise TypeError("source factory must be callable")
        if key in self._source_factories:
            raise PluginError(f"source factory {key!r} was registered more than once by this plugin")
        self._source_factories[key] = factory


class PluginRegistry:
    """Registry for optional adapter/source factories supplied by plugins.

    Entry points are loaded only when ``load_entry_points`` is explicitly
    called. Loading executes installed Python code in this process; this is
    discovery/version checking, not a sandbox.
    """

    def __init__(self) -> None:
        self._source_factories: dict[str, Callable[..., ObservationSource]] = {}
        self._plugins: dict[str, str] = {}

    @property
    def installed_plugins(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    @property
    def source_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._source_factories))

    def register(self, plugin: EnginePlugin) -> None:
        name = _normalize_name(getattr(plugin, "name", ""), "plugin")
        api_version = str(getattr(plugin, "api_version", ""))
        callback = getattr(plugin, "register", None)
        if not callable(callback):
            raise PluginError("plugin must provide a callable register(registry) method")
        if api_version != PLUGIN_API_VERSION:
            raise PluginCompatibilityError(
                f"plugin {name!r} targets API {api_version!r}; this engine supports {PLUGIN_API_VERSION!r}"
            )
        if name in self._plugins:
            raise PluginError(f"plugin {name!r} is already registered")

        staged = PluginContributions()
        try:
            callback(staged)
        except Exception as error:
            raise PluginLoadError(f"plugin {name!r} failed during registration: {error}") from error
        collisions = sorted(set(staged._source_factories) & set(self._source_factories))
        if collisions:
            raise PluginError(f"plugin {name!r} conflicts with registered source name(s): {', '.join(collisions)}")
        self._source_factories.update(staged._source_factories)
        self._plugins[name] = api_version

    def create_source(self, name: str, **configuration: Any) -> ObservationSource:
        key = _normalize_name(name, "source")
        try:
            factory = self._source_factories[key]
        except KeyError:
            raise KeyError(f"no source factory registered as {key!r}; available: {', '.join(self.source_names) or '(none)'}") from None
        source = factory(**configuration)
        if any(not callable(getattr(source, method, None)) for method in ("open", "read_batch", "close")):
            raise PluginError(f"source factory {key!r} did not return an ObservationSource")
        return source

    @classmethod
    def load_entry_points(cls, *, group: str = ENTRY_POINT_GROUP) -> "PluginRegistry":
        """Load plugins advertised in package metadata; failures are explicit."""
        registry = cls()
        for point in sorted(entry_points(group=group), key=lambda item: item.name):
            try:
                exported = point.load()
                if inspect.isclass(exported) or (callable(exported) and not callable(getattr(exported, "register", None))):
                    exported = exported()
                registry.register(exported)
            except Exception as error:
                if isinstance(error, PluginLoadError):
                    raise PluginLoadError(f"entry point {point.name!r}: {error}") from error
                raise PluginLoadError(f"could not load entry point {point.name!r}: {error}") from error
        return registry


def _normalize_name(value: Any, kind: str) -> str:
    if not isinstance(value, str):
        raise PluginError(f"{kind} name must be a string")
    name = value.strip().lower()
    if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,62}", name):
        raise PluginError(f"{kind} name must match [a-z][a-z0-9_.-]{{0,62}}")
    return name


__all__ = [
    "ENTRY_POINT_GROUP",
    "PLUGIN_API_VERSION",
    "EnginePlugin",
    "PluginCompatibilityError",
    "PluginContributions",
    "PluginError",
    "PluginLoadError",
    "PluginRegistry",
]
