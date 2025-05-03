# Web Server & REST API in NekoConf

NekoConf includes a FastAPI-based web server for remote configuration management, a REST API, and a simple web UI.

## Starting the Server

```python
from nekoconf import NekoConfigManager, NekoConfigServer
config = NekoConfigManager("config.yaml")
server = NekoConfigServer(config, api_key="your-secret-key")
server.run(host="0.0.0.0", port=8000)
```

Or via CLI:

```bash
nekoconf server --config config.yaml --port 8000 --api-key your-secret-key
```

## Web UI

- Access the UI at `http://localhost:8000`.
- Login with your API key if enabled.
- View and edit configuration in your browser.

## REST API Reference

| Endpoint                  | Method | Description                        |
|--------------------------|--------|------------------------------------|
| `/api/config`            | GET    | Get entire configuration           |
| `/api/config/{path}`     | GET    | Get specific config value          |
| `/api/config/{path}`     | POST   | Set config value                   |
| `/api/config/{path}`     | DELETE | Delete config value                |
| `/api/config/validate`   | POST   | Validate config against schema     |
| `/api/config/reload`     | POST   | Reload config from file            |
| `/health`                | GET    | Health check                       |
| `/ws`                    | WS     | WebSocket for real-time updates    |

### Example: Get a Value

```bash
curl -H "Authorization: Bearer your-secret-key" http://localhost:8000/api/config/database.host
```

### Example: Set a Value

```bash
curl -X POST -H "Authorization: Bearer your-secret-key" \
     -H "Content-Type: application/json" \
     -d '{"value": "newhost.example.com"}' \
     http://localhost:8000/api/config/database.host
```

### Example: WebSocket

Connect to `ws://localhost:8000/ws` to receive real-time config updates.

## Security

- Use the `--api-key` option or `api_key` argument to require authentication.
- API key can be sent as `Authorization: Bearer <key>` header or as a cookie.
- Exclude `/docs`, `/redoc`, `/openapi.json`, and `/health` from auth for diagnostics.

[!WARNING]
Always set an API key in production. Without it, anyone can modify your configuration.

## Read-Only Mode

Start the server with `--read-only` to disable all write operations:

```bash
nekoconf server --read-only
```

[!TIP]
Use the REST API for integration with CI/CD, monitoring, or remote management tools.
