# Advanced Usage: NekoConf

This guide covers advanced NekoConf features for power users and integrators.

## Concurrency & Locking

NekoConf uses file locks to prevent race conditions when multiple processes or threads access the same config file.

- All file operations are protected by a lock (see `LockManager`).
- Locks are automatically cleaned up on exit or signal.
- For custom workflows, use the config manager as a context manager:

```python
with NekoConfigManager("config.yaml") as config:
    config.set("key", "value")
    config.save()
```

[!NOTE]
If you see lock file errors, ensure all processes use NekoConf APIs for access.

## Dynamic Reload in Long-Running Apps

- Use `config.reload()` to re-read config from disk and apply environment overrides.
- Register event handlers to react to reloads:

```python
@config.on_event(EventType.RELOAD)
def on_reload(**kwargs):
    print("Configuration reloaded!")
```

## Integration with Other Frameworks

- **Flask, FastAPI, Django:** See integration examples in the main README.
- **Celery/Background Workers:** Reload config or update settings on change events.
- **Microservices:** Use the REST API or WebSocket for centralized config updates.

## WebSocket Real-Time Updates

- Connect to `/ws` for push notifications of config changes.
- Example (Python):

```python
import websockets
import asyncio
import json

async def listen():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print("Config update:", data)

asyncio.run(listen())
```

## Deep Merge vs. Shallow Update

- By default, `update()` performs a deep merge of nested dictionaries.
- To overwrite top-level keys only, use `deep_merge=False`:

```python
config.update({"logging": {"level": "INFO"}}, deep_merge=False)
```

## Troubleshooting

- Use `--debug` with the CLI for verbose logs.
- Check for lock file cleanup if you see access errors.
- Use schema validation to catch config errors early.

[!TIP]
Combine event handlers, environment overrides, and the REST API for maximum flexibility in modern deployments.
