# Event System in NekoConf

NekoConf provides a powerful event system that lets your application react instantly to configuration changes, enabling dynamic reloading, feature toggling, and more.

## Core Concepts

- **on_change(path_pattern):** React to any change on a specific config path or pattern.
- **on_event(event_type, path_pattern):** React to specific event types (CREATE, UPDATE, DELETE, RELOAD, VALIDATE) and paths.
- **Priority:** Handlers can be prioritized (lower number = higher priority).

## Usage Examples

### Basic Change Handler

```python
from nekoconf import NekoConfigManager
config = NekoConfigManager("config.yaml")

@config.on_change("database.*")
def handle_db_change(event_type, path, old_value, new_value, config_data, **kwargs):
    print(f"Database config {path} changed: {old_value} -> {new_value}")
```

### Handling Specific Event Types

```python
from nekoconf import EventType

@config.on_event([EventType.CREATE, EventType.UPDATE], "features.*")
def feature_flag_handler(event_type, path, new_value, **kwargs):
    print(f"Feature flag {path} {event_type.value}: {new_value}")
```

### Advanced: Multiple Handlers and Priorities

```python
@config.on_change("logging.level", priority=10)
def update_logging_level(event_type, path, old_value, new_value, config_data, **kwargs):
    # Set log level before other handlers
    ...

@config.on_change("logging.*", priority=100)
def generic_logging_change(event_type, path, old_value, new_value, config_data, **kwargs):
    ...
```

## Event Types Table

| EventType   | Description                                 |
|-------------|---------------------------------------------|
| CHANGE      | Any change to configuration                 |
| CREATE      | New key created                             |
| UPDATE      | Existing key updated                        |
| DELETE      | Key deleted                                 |
| RELOAD      | Configuration reloaded from disk            |
| VALIDATE    | Configuration validated                     |

## Real-World Use Cases

- **Hot-reload database connections**
- **Dynamic feature flags**
- **Live update of logging levels**
- **Cache invalidation on config change**

[!TIP]
Combine event handlers with async functions for non-blocking updates.

## Best Practices

- Use specific path patterns to avoid unnecessary handler calls.
- Use priorities to control handler execution order.
- Always handle exceptions in your handlers to avoid breaking the event pipeline.

[!NOTE]
See the main README and [Advanced Usage](advanced-usage.md) for integration patterns with frameworks and async event handling.
