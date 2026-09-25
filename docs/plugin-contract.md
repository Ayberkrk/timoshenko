# Plugin contract (0.11)

Timoshenko supports explicit source-factory registration and opt-in Python entry-point discovery. Plugins are packaged separately so protocol libraries remain optional.

```python
from timoshenko import PLUGIN_API_VERSION

class MyGatewayPlugin:
    name = "my-gateway"
    api_version = PLUGIN_API_VERSION

    def register(self, registry):
        registry.register_source("my-gateway", MyGatewaySource)
```

An adapter distribution advertises its plugin through package metadata:

```toml
[project.entry-points."timoshenko.plugins"]
my_gateway = "my_gateway.plugin:MyGatewayPlugin"
```

Applications choose when to load installed code:

```python
registry = tm.PluginRegistry.load_entry_points()
source = registry.create_source("my-gateway", endpoint="opc.tcp://host:4840")
```

The entry point may expose a plugin instance, a class with a zero-argument constructor, or a zero-argument factory returning a plugin. Each plugin declares `name` and `api_version`; the current API is `"1"`. The engine rejects incompatible APIs, invalid names, duplicate plugin/source names, and malformed source factories. Each plugin registers into a staging area, so a registration exception cannot leave that plugin's partial source registrations behind. Loading stops with `PluginLoadError` rather than silently skipping broken or incompatible code.

Entry-point loading is explicit and executes installed Python code in the application process. It is not a security sandbox; only install plugins the application owner trusts. Discovery performs no source connection. Source instances acquire external resources only when `SessionRunner` calls `open()` and must release them in `close()`. Protocol authentication, reconnect/backoff, parsing, timeout, and transport-to-observation mappings belong to the adapter.

The first plugin API registers observation-source factories only. Analyzer, model, storage, and report renderer plugin families need their own versioned contracts before being added.
