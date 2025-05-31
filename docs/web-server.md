# Configuration Orchestrator in NekoConf

NekoConf includes a FastAPI-based configuration orchestrator for managing multiple application configurations, with REST API endpoints and real-time WebSocket updates.

## Overview

The NekoConfOrchestrator manages multiple NekoConf instances, each identified by a unique app name. This allows you to centrally manage configurations for multiple applications, microservices, or environments.

## Starting the Orchestrator

### With Pre-configured Apps

```python
from nekoconf import NekoConf
from nekoconf.server.app import NekoConfOrchestrator

# Create configurations for different apps
apps = {
    "web-frontend": NekoConf({"server": {"port": 3000}, "debug": True}),
    "api-backend": NekoConf({"database": {"host": "localhost", "port": 5432}}),
    "user-service": NekoConf({"service": {"name": "user-service", "version": "1.0.0"}})
}

orchestrator = NekoConfOrchestrator(
    apps=apps,
    api_key="your-secret-key",
    read_only=False
)
orchestrator.run(host="0.0.0.0", port=8000)
```

### Empty Orchestrator (Create Apps via API)

```python
from nekoconf.server.app import NekoConfOrchestrator

# Start with no apps - create them via API
orchestrator = NekoConfOrchestrator(api_key="your-secret-key")
orchestrator.run(host="0.0.0.0", port=8000)
```

### Via CLI (Backward Compatibility)

```bash
# Creates a "default" app with the specified config file
nekoconf server --config config.yaml --port 8000 --api-key your-secret-key
```

## Web UI

- Access the UI at `http://localhost:8000`
- Login with your API key if enabled
- View and manage multiple app configurations

## REST API Reference

### App Management

| Endpoint                     | Method | Description                    |
|------------------------------|--------|--------------------------------|
| `/api/apps`                  | GET    | List all managed apps          |
| `/api/apps/{app_name}`       | POST   | Create new app                 |
| `/api/apps/{app_name}`       | DELETE | Delete app                     |

### App Configuration

| Endpoint                                | Method | Description                        |
|-----------------------------------------|--------|------------------------------------|
| `/api/apps/{app_name}/config`          | GET    | Get entire app configuration       |
| `/api/apps/{app_name}/config/{path}`   | GET    | Get specific config value          |
| `/api/apps/{app_name}/config`          | POST   | Update app configuration           |
| `/api/apps/{app_name}/config/{path}`   | POST   | Set specific config value          |
| `/api/apps/{app_name}/config/{path}`   | DELETE | Delete config value                |
| `/api/apps/{app_name}/reload`          | POST   | Reload app config                  |
| `/api/apps/{app_name}/validate`        | POST   | Validate app config                |

### System

| Endpoint  | Method | Description                           |
|-----------|--------|---------------------------------------|
| `/health` | GET    | Health check (includes app count)     |

### WebSocket

| Endpoint           | Protocol | Description                           |
|--------------------|----------|---------------------------------------|
| `/ws/{app_name}`   | WS       | Real-time updates for specific app   |

## API Examples

### List All Apps

```bash
curl http://localhost:8000/api/apps
```

Response:
```json
{
  "apps": ["web-frontend", "api-backend", "user-service"]
}
```

### Create New App

```bash
curl -X POST -H "Content-Type: application/json" \
     -H "Authorization: Bearer your-secret-key" \
     -d '{"debug": true, "env": "development"}' \
     http://localhost:8000/api/apps/new-service
```

### Get App Configuration

```bash
curl -H "Authorization: Bearer your-secret-key" \
     http://localhost:8000/api/apps/web-frontend/config
```

### Update App Configuration

```bash
curl -X POST -H "Authorization: Bearer your-secret-key" \
     -H "Content-Type: application/json" \
     -d '{"server": {"port": 3001}, "debug": false}' \
     http://localhost:8000/api/apps/web-frontend/config
```

### Set Specific Value

```bash
curl -X POST -H "Authorization: Bearer your-secret-key" \
     -H "Content-Type: application/json" \
     -d '{"value": "production"}' \
     http://localhost:8000/api/apps/web-frontend/config/environment
```

### WebSocket Connection

Connect to `ws://localhost:8000/ws/web-frontend` to receive real-time updates for the "web-frontend" app.

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/web-frontend');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'config') {
        console.log('Initial config:', data.data);
    } else if (data.type === 'update') {
        console.log('Config updated:', data.data);
    }
};
```

## Remote Client Usage

### Using RemoteStorageBackend

```python
from nekoconf import NekoConf
from nekoconf.storage.remote import RemoteStorageBackend

# Connect to specific app on remote orchestrator
storage = RemoteStorageBackend(
    remote_url="http://config-server:8000",
    app_name="web-frontend",
    api_key="your-secret-key"
)

config = NekoConf(storage=storage, event_emission_enabled=True)

# Get configuration
print("Current config:", config.get())

# Set up change listener for real-time updates
@config.on_change("*")
def on_change(**kwargs):
    print("Configuration changed!")
    print("New config:", config.get())

# Update configuration
config.set("debug", False)
config.save()
```

### Using CLI

```bash
# Connect to specific app
nekoconf connect http://config-server:8000 --app-name web-frontend --watch

# Connect with API key
nekoconf connect http://config-server:8000 \
    --app-name api-backend \
    --api-key your-secret-key \
    --watch
```

## App Naming Rules

- App names must be 1-64 characters long
- Must start with alphanumeric character
- Can contain letters, numbers, hyphens, and underscores
- Case-sensitive
- Must be unique within the orchestrator

Valid examples: `web-frontend`, `api_backend`, `UserService`, `service-v2`

## Security

- Use the `--api-key` option or `api_key` parameter to require authentication
- API keys are validated for all write operations
- Each app's configuration is isolated from others
- WebSocket connections are app-specific

## Migration from Single-Instance Server

The orchestrator maintains backward compatibility:

1. **CLI**: Using `nekoconf server --config file.yaml` creates a "default" app
2. **API**: Legacy endpoints can be mapped to the "default" app
3. **Code**: Replace `NekoConfOrchestrator` with `NekoConfOrchestrator`

Example migration:

```python
# Old single-instance server
from nekoconf.server.app import NekoConfOrchestrator
config = NekoConf("config.yaml")
server = NekoConfOrchestrator(config)

# New orchestrator (backward compatible)
from nekoconf.server.app import NekoConfOrchestrator
apps = {"default": NekoConf("config.yaml")}
orchestrator = NekoConfOrchestrator(apps)
```
