# NekoConf

<div align="center">
  <img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/banner.png" width="800" />
  
  <h3>The purr-fect balance of power and simplicity for configuration management.</h3>
  
  <!-- Language versions -->
  <p>
    <a href="README.md">🇺🇸 English</a> |
    <a href="README_zh.md">🇨🇳 中文</a> |
    <a href="README_ja.md">🇯🇵 日本語</a>
  </p>
  
  <div>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/v/nekoconf.svg" alt="PyPI version"/></a>
    <a href="https://pypi.org/project/nekoconf/"><img src="https://img.shields.io/pypi/pyversions/nekoconf.svg" alt="Python versions"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/blob/main/LICENSE"><img src="https://img.shields.io/github/license/nya-foundation/nekoconf.svg" alt="License"/></a>
    <a href="https://pepy.tech/projects/nekoconf"><img src="https://static.pepy.tech/badge/nekoconf" alt="PyPI Downloads"/></a>
    <a href="https://hub.docker.com/r/k3scat/nekoconf"><img src="https://img.shields.io/docker/pulls/k3scat/nekoconf" alt="Docker Pulls"/></a>
    <a href="https://deepwiki.com/Nya-Foundation/NekoConf"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"/></a>
  </div>
  
  <div>
    <a href="https://codecov.io/gh/nya-foundation/nekoconf"><img src="https://codecov.io/gh/nya-foundation/nekoconf/branch/main/graph/badge.svg" alt="Code Coverage"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/scan.yml/badge.svg" alt="CodeQL & Dependencies Scan"/></a>
    <a href="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml"><img src="https://github.com/nya-foundation/nekoconf/actions/workflows/publish.yml/badge.svg" alt="CI/CD Builds"/></a>
  </div>
</div>

## 🐱 What is NekoConf?

> [!WARNING]
> This project is currently under active development. Documentation may not reflect the latest changes. If you encounter unexpected behavior, please consider using a previous stable version or report issues on our GitHub repository.

NekoConf is a dynamic and flexible configuration management system for Python applications. It simplifies handling configuration files (YAML, JSON, TOML) and provides real-time updates, environment variable overrides, and schema validation.

| Feature                      | Description                                                                 |
| ---------------------------- | --------------------------------------------------------------------------- |
| **Configuration as Code**    | Store configuration in human-readable YAML, JSON, or TOML files.            |
| **Centralized Management**   | Access and modify configuration via a Python API, CLI, or optional Web UI.  |
| **Dynamic Updates**          | React instantly to configuration changes using a built-in event system.     |
| **Environment Overrides**    | Seamlessly override file settings with environment variables.               |
| **Schema Validation**        | Ensure configuration integrity and prevent errors using JSON Schema.        |
| **Concurrency Safe**         | Uses file locking to prevent race conditions during file access.            |
| **Remote Configuration**     | Connect to a remote NekoConf server for centralized configuration.          |

> [!TIP]
> NekoConf is ideal for applications with complex configuration needs, microservice architectures, or any scenario where you need to update configuration without service restarts.

## 🛠️ Prerequisites
- Python 3.10 or higher
- Docker (optional, for containerized deployment)

## 📦 Installation

NekoConf follows a modular design with optional dependencies for different features:

```bash
# Basic installation with core features (local)
pip install nekoconf

# With webui server (FastAPI-based)
pip install nekoconf[server]

# With schema validation
pip install nekoconf[schema]

# With remote client (conntect to a NekoConf server)
pip install nekoconf[remote]

# For development and testing
pip install nekoconf[dev]

# Install all optional features
pip install nekoconf[all]
```

### Optional Features

| Feature                | Extra          | Dependencies                                        | Purpose                                                   |
|------------------------|----------------|----------------------------------------------------|------------------------------------------------------------|
| **Core**               | (none)         | pyyaml, colorlog, tomli, tomli-w                    | Basic configuration operations                             |
| **Web Server/API**     | `server`       | fastapi, uvicorn, etc.                     | Run a web server to manage configuration                  |
| **Schema Validation**  | `schema`       | jsonschema, rfc3987                                | Validate configuration against JSON Schema                |
| **Remote Config**      | `remote`       | requests, websocket-client                         | Connect to a remote NekoConf server                       |
| **Development Tools**  | `dev`          | pytest, pytest-cov, etc.                           | For development and testing                               |
| **All Features**       | `all`          | All of the above                                   | Complete installation with all features                   |

## 🚀 Quick Start

```python
from nekoconf import NekoConf

# Initialize with configuration file path (creates file if it doesn't exist)
config = NekoConf("config.yaml", event_emission_enabled=True)

# Register a handler to react to configuration changes
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"Database configuration changed: {path}")
    print(f"  {old_value} -> {new_value}")
    # Reconnect to database or apply changes...

# Get configuration values (supports nested keys with dot notation)
db_host = config.get("database.host", default="localhost")
db_port = config.get("database.port", default=5432)

# Set configuration values
config.set("database.pool_size", 10) # trigger `handle_db_change`
config.set("features.dark_mode", True) # won't trigger `handle_db_change`

# Save changes to file
config.save()
```

## 🔧 Core Features

### 🔄 Configuration Management

Load, access, and modify configuration data using dot notation expressions.

```python
sample_config = {
    "database": {
        "host": "127.0.0.1",
        "port": "8080"
    },
    "features": {
        "enabled": False
    }
}

# in-memory configuration for demo purposes
config = NekoConf(sample_config)

# Access values with type conversion
host = config.get("database.host") # "127.0.0.1"
port = config.get_int("database.port", default=5432) # 8080
is_enabled = config.get_bool("features.enabled", default=False) # False

# Update multiple values at once, or use replace to set the entire config
config.update({
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(levelname)s - %(message)s"
    }
})
print(config.json()) 
```

### 🌍 Environment Variable Overrides

Override configuration with environment variables. By default, variables are mapped as:
`database.host` → `NEKOCONF_DATABASE_HOST`

```bash
# Override configuration values with environment variables
export NEKOCONF_DATABASE_HOST=production-db.example.com
export NEKOCONF_DATABASE_PORT=5433
export NEKOCONF_FEATURES_ENABLED=true
```

```python
# These values will reflect environment variables automatically
config = NekoConf("config.yaml", env_override_enabled=True)
print(config.get("database.host"))  # "production-db.example.com" 
print(config.get_int("database.port"))  # 5433
print(config.get_bool("features.enabled"))  # True
```
You can customize the environment variable prefix and delimiter:

```python
config = NekoConf(
    "config.yaml",
    env_override_enabled=True
    env_prefix="MYAPP",
    env_nested_delimiter="_"
)
```

The above would overwrite `database.host` with `MYAPP_DATABASE_HOST`.

### 📢 Event System

React to configuration changes in real-time:

```python
from nekoconf import NekoConf, EventType

config = NekoConf("config.yaml", event_emission_enabled=True)

# React to any change to database configuration
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"Database config {path} changed: {old_value} -> {new_value}")

# React to specific event types
@config.on_event([EventType.CREATE, EventType.UPDATE], "cache.*")
def handle_cache_config(event_type, path,new_value, **kwargs):
    if event_type == EventType.CREATE:
        print(f"New cache setting created: {path} = {new_value}")
    else:
        print(f"Cache setting updated: {path} = {new_value}")

# Change configuration to trigger events
config.set("database.timeout", 30)  # Triggers handle_db_change
config.set("cache.ttl", 600)  # Triggers handle_cache_config Create event
config.set("cache.ttl", 300)  # Triggers handle_cache_config Update event
```

### 🌐 Remote Configuration

Connect to a remote NekoConf server for centralized configuration (requires `nekoconf[remote]`):

```python
from nekoconf import NekoConf, RemoteStorageBackend

remote_storage = RemoteStorageBackend(
    url="https://config-server.example.com/api/config",
    app_name="CustomApp"
    api_key="secure-key",
)

config = NekoConf(
    storage=remote_storage,  # Use remote storage backend
    event_emission_enabled=True # Enable event observer 
)

# Use exactly the same API as with local files
db_host = config.get("database.host")

# React to changes from the remote server
@config.on_change("features.*")
def handle_feature_change(path, new_value, **kwargs):
    print(f"Feature flag changed: {path} = {new_value}")
    # Apply feature change...

# Set a new value
config.set("features.dark_mode", True) # This will trigger the `handle_feature_change` callback
```

### ✅ Schema Validation

Ensure configuration integrity using JSON Schema (requires `nekoconf[schema]`):

```python
# schema.json
{
    "type": "object",
    "properties": {
        "database": {
            "type": "object",
            "required": ["host", "port"],
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer", "minimum": 1024}
            }
        }
    },
    "required": ["database"]
}
```

```python
# Initialize with schema
config = NekoConf("config.yaml", schema_path="schema.json")

# Validate configuration
errors = config.validate()
if errors:
    for error in errors:
        print(f"Error: {error}")
    
# Set invalid value and validate
config.set("database.port", "not-a-port")
errors = config.validate()
print(errors)  # Shows validation error
```

## 🖥️ Web UI & REST API

NekoConf includes a web server built with FastAPI to manage configuration remotely (requires `nekoconf[server]`):

```python
from nekoconf import NekoConf, NekoConfOrchestrator

config = NekoConf("config.yaml")
apps = {
    "My_Config_Server": config
    # add more config app instances as needed
}
server = NekoConfOrchestrator(apps, api_key="secure-key", read_only=False)
server.run(host="0.0.0.0", port=8000)
```

### Integrating with Existing FastAPI Applications

You can also mount the NekoConf orchestrator into your existing FastAPI application:

```python
from fastapi import FastAPI
from nekoconf import NekoConf, NekoConfOrchestrator

# Your existing FastAPI app
app = FastAPI(title="My Application")

@app.get("/")
def read_root():
    return {"message": "Hello from my main app!"}

# Create NekoConf orchestrator
config = NekoConf("config.yaml")
apps = {"MyApp": config}
orchestrator = NekoConfOrchestrator(apps, api_key="secure-key")

# Mount the configuration orchestrator under /config
app.mount("/config", orchestrator.app)

# Now your app serves both your endpoints and config management:
# - http://localhost:8000/ - Your main app
# - http://localhost:8000/config/ - Configuration dashboard
# - http://localhost:8000/config/docs - Configuration API docs
# - http://localhost:8000/config/api/apps - Configuration API endpoints

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

Access at http://localhost:8000 for the web UI or use REST endpoints:

> [!TIP]
> **Interactive API Documentation**: FastAPI automatically generates interactive API documentation available at:
> - **Swagger UI**: http://localhost:8000/docs 
> - **ReDoc**: http://localhost:8000/redoc
> 
> These provide a complete interactive interface to test all API endpoints directly from your browser.

### Health & System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and system status |

### App Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/apps` | GET | List all managed apps with their information |
| `/api/apps` | POST | Create a new configuration app |
| `/api/apps/{app_name}` | GET | Get information about a specific app |
| `/api/apps/{app_name}` | PUT | Update an app's configuration and metadata |
| `/api/apps/{app_name}` | DELETE | Delete an app and clean up its resources |
| `/api/apps/{app_name}/metadata` | PATCH | Update app metadata (name and/or description) |

### Configuration Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/apps/{app_name}/config` | GET | Get entire configuration for a specific app |
| `/api/apps/{app_name}/config` | PUT | Update entire configuration for a specific app |
| `/api/apps/{app_name}/config/{path}` | GET | Get specific configuration value by path |
| `/api/apps/{app_name}/config/{path}` | PUT | Set specific configuration value by path |
| `/api/apps/{app_name}/config/{path}` | DELETE | Delete specific configuration value by path |
| `/api/apps/{app_name}/validate` | POST | Validate configuration against schema |

### WebSocket Endpoints

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/ws/{app_name}` | WebSocket | Real-time configuration updates for specific app |

### Static File Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve orchestrator dashboard |
| `/{app_name}` | GET | Serve configuration page for specific app |
| `/static/{file_path}` | GET | Serve static assets (CSS, JS, images) |
| `/favicon.ico` | GET | Serve favicon |

The server supports WebSocket connections for real-time configuration updates on a per-app basis.

> [!WARNING]
> Secure your API with an API key in production environments.

### Web UI Showcases

<div align="center">

**Configuration Management Interface**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/config_app.png" width="700" />

**Dashboard & Overview**
<img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/dashboard.png" width="700" />

</div>

## 💻 Command-Line Interface

NekoConf provides a comprehensive command-line interface for managing configuration:

### Basic Usage

```bash
# View help and version
nekoconf --help
nekoconf --version

# Enable debug logging for any command
nekoconf --debug <command>
```

### Server Management

```bash
# Start web server (requires nekoconf[server])
nekoconf server --config config.yaml --port 8000 --api-key "secure-key"

# Start server with additional options
nekoconf server \
  --host 0.0.0.0 \
  --port 8000 \
  --config config.yaml \
  --schema schema.json \
  --api-key "secure-key" \
  --app-name "MyApp" \
  --event true \
  --read-only false \
  --reload true
```

### Configuration Management

```bash
# Initialize new configuration with templates
nekoconf init config.yaml --template default
nekoconf init api-config.yaml --template api-service
nekoconf init web-config.yaml --template web-app
nekoconf init micro-config.yaml --template microservice
nekoconf init empty-config.yaml --template empty

# Get configuration value
nekoconf get database.host --config config.yaml

# Get entire configuration with different formats
nekoconf get --config config.yaml --format json
nekoconf get --config config.yaml --format yaml
nekoconf get --config config.yaml --format raw

# Set configuration value
nekoconf set database.port 5432 --config config.yaml

# Set with schema validation
nekoconf set database.port 5432 --config config.yaml --schema schema.json

# Delete configuration value
nekoconf delete old.setting --config config.yaml

# Validate configuration (requires nekoconf[schema])
nekoconf validate --config config.yaml --schema schema.json
```

### Remote Configuration

```bash
# Connect to a remote NekoConf server (requires nekoconf[remote])
nekoconf connect --remote http://config-server:8000 --api-key "secure-key" --format json

# Connect with specific app name
nekoconf connect --remote http://config-server:8000 --app-name "MyApp" --api-key "secure-key"

# Get value from remote server
nekoconf get database.host --remote http://config-server:8000 --api-key "secure-key"

# Set value on remote server
nekoconf set cache.ttl 600 --remote http://config-server:8000 --api-key "secure-key"

# Delete value on remote server
nekoconf delete old.setting --remote http://config-server:8000 --api-key "secure-key"

# Validate remote configuration
nekoconf validate --remote http://config-server:8000 --api-key "secure-key" --schema schema.json
```

### Configuration Templates

The `init` command supports several built-in templates:

| Template | Description | Use Case |
|----------|-------------|----------|
| `empty` | 📄 Empty Configuration | Start with a blank configuration |
| `default` | ⚙️ Default Configuration | Basic configuration template |
| `web-app` | 🌐 Web Application | Frontend application with server and API settings |
| `api-service` | 🔌 API Service | Backend service with database and auth configuration |
| `microservice` | 🐳 Microservice | Containerized service with logging and metrics |

## ❤️ Discord Community

[![Discord](https://img.shields.io/discord/1365929019714834493)](https://discord.gg/jXAxVPSs7K)

> [!NOTE]
> Need support? Contact [k3scat@gmail.com](mailto:k3scat@gmail.com) or join our discord community at [Nya Foundation](https://discord.gg/jXAxVPSs7K)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.