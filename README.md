# NekoConf

<div align="center">
  <img src="https://raw.githubusercontent.com/Nya-Foundation/nekoconf/main/assets/banner.png" width="800" />
  
  <h3>The purr-fect balance of power and simplicity for configuration management.</h3>
  
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

> [!NOTE]
> This project is currently in beta. We welcome feedback and contributions!

## 🛠️ Prerequisites
- Python 3.11 or higher
- Docker (optional, for containerized deployment)

## 📦 Installation

NekoConf follows a modular design with optional dependencies for different features:

```bash
# Basic installation with core features
pip install nekoconf

# With web server (FastAPI-based)
pip install nekoconf[server]

# With schema validation
pip install nekoconf[schema]

# With remote configuration support
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
| **Web Server/API**     | `server`       | fastapi, uvicorn, jinja2, etc.                     | Run a web server to manage configuration                  |
| **Schema Validation**  | `schema`       | jsonschema, rfc3987                                | Validate configuration against JSON Schema                |
| **Remote Config**      | `remote`       | requests, websocket-client                         | Connect to a remote NekoConf server                       |
| **Development Tools**  | `dev`          | pytest, pytest-cov, etc.                           | For development and testing                               |
| **All Features**       | `all`          | All of the above                                   | Complete installation with all features                   |

## 🚀 Quick Start

```python
from nekoconf import NekoConf

# Initialize with configuration file path (creates file if it doesn't exist)
config = NekoConf("config.yaml", event_emission_enabled=True)

# Get configuration values (supports nested keys with dot notation)
db_host = config.get("database.host", default="localhost")
db_port = config.get("database.port", default=5432)

# Set configuration values
config.set("database.pool_size", 10)
config.set("features.dark_mode", True)

# Save changes to file
config.save()

# Register a handler to react to configuration changes
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"Database configuration changed: {path}")
    print(f"  {old_value} -> {new_value}")
    # Reconnect to database or apply changes...
```

## 🔧 Core Features

### 🔄 Configuration Management

Load, access, and modify configuration data using dot notation expressions.

```python
# Load configuration from file (happens automatically on initialization)
config = NekoConf("config.yaml")

# Access values with type conversion
host = config.get("database.host")
port = config.get_int("database.port", default=5432)
is_enabled = config.get_bool("features.enabled", default=False)

# Update multiple values at once
config.update({
    "logging": {
        "level": "DEBUG",
        "format": "%(asctime)s - %(levelname)s - %(message)s"
    }
})

# Save to file
config.save()
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
config = NekoConf("config.yaml")
print(config.get("database.host"))  # "production-db.example.com" 
print(config.get_int("database.port"))  # 5433
print(config.get_bool("features.enabled"))  # True
```

You can customize the environment variable prefix and delimiter:

```python
config = NekoConf(
    "config.yaml",
    env_prefix="MYAPP",
    env_nested_delimiter="_"
)
```

The above would map `database.host` to `MYAPP_DATABASE_HOST`.

> [!NOTE]
> See [Environment Variables](docs/environment-variables.md) for more advanced configuration options.

### 📢 Event System

React to configuration changes in real-time:

```python
from nekoconf import NekoConf, EventType

config = NekoConf("config.yaml", event_emission_enabled=True)

# React to any change to database configuration
@config.on_change("database.*")
def handle_db_change(path, old_value, new_value, **kwargs):
    print(f"Database config {path} changed: {old_value} -> {new_value}")
    # Reconnect to database or apply the change

# React to specific event types
@config.on_event([EventType.CREATE, EventType.UPDATE], "cache.*")
def handle_cache_config(path, new_value, **kwargs):
    if event_type == EventType.CREATE:
        print(f"New cache setting created: {path} = {new_value}")
    else:
        print(f"Cache setting updated: {path} = {new_value}")
    # Update cache settings...

# Change configuration to trigger events
config.set("database.timeout", 30)  # Triggers handle_db_change
config.set("cache.ttl", 600)  # Triggers handle_cache_config
```

For more advanced event patterns, see [Event Handling](docs/event-system.md).

### 🌐 Remote Configuration

Connect to a remote NekoConf server for centralized configuration (requires `nekoconf[remote]`):

```python
# Connect to a remote NekoConf server
config = NekoConf(
    remote_url="https://config-server.example.com",
    remote_api_key="secure-key",
    remote_read_only=True,  # Only read from server, don't push changes back
    in_memory=True,  # No local file, purely in-memory
    event_emission_enabled=True # Enable event observer 
)

# Use exactly the same API as with local files
db_host = config.get("database.host")

# React to changes from the remote server
@config.on_change("features.*")
def handle_feature_change(path, new_value, **kwargs):
    print(f"Feature flag changed: {path} = {new_value}")
    # Apply feature change...
```

You can also combine remote configuration with local files:

```python
# Use remote configuration with local backup file
config = NekoConf(
    config_path="local-backup.yaml",  # Local backup file
    remote_url="https://config-server.example.com",
    remote_api_key="secure-key",
    remote_read_only=False  # Can push changes back to server
)

# Changes are first pushed to the remote server, then saved locally
config.set("api.timeout", 30)
config.save()
```

For more details and options, see [Remote Configuration](docs/remote-configuration.md).

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
server = NekoConfOrchestrator(config, api_key="secure-key")
server.run(host="0.0.0.0", port=8000)
```

Access at http://localhost:8000 for the web UI or use REST endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | Get entire configuration |
| `/api/config/{path}` | GET | Get specific configuration value |
| `/api/config/{path}` | POST | Set configuration value |
| `/api/config/{path}` | DELETE | Delete configuration value |
| `/api/config/validate` | POST | Validate configuration against schema |
| `/api/config/reload` | POST | Reload configuration from file |

The server also supports WebSocket connections for real-time configuration updates.

> [!WARNING]
> Secure your API with an API key in production environments.

Learn more about the [Web Server and REST API](docs/web-server.md).

## 💻 Command-Line Interface

NekoConf provides a command-line interface for managing configuration:

```bash
# View help
nekoconf --help

# Start web server (requires nekoconf[server])
nekoconf server --config config.yaml --port 8000 --api-key "secure-key"

# Get configuration value
nekoconf get database.host --config config.yaml

# Get entire configuration as JSON
nekoconf get --config config.yaml --format json

# Set configuration value
nekoconf set database.port 5432 --config config.yaml

# Delete configuration value
nekoconf delete old.setting --config config.yaml

# Validate configuration (requires nekoconf[schema])
nekoconf validate --config config.yaml --schema schema.json

# Import configuration from another file
nekoconf import new-values.json --config config.yaml

# Connect to a remote NekoConf server (requires nekoconf[remote])
nekoconf connect http://config-server:8000 --api-key "secure-key" --watch
```

### Remote Configuration via CLI

You can connect to a remote NekoConf server directly from the command line:

```bash
# Connect to a remote server and watch for config changes
nekoconf connect http://config-server:8000 --watch --format json

# Get a value from remote server
nekoconf get api.timeout --remote-url http://config-server:8000 --remote-api-key "secure-key"

# Update a value on the remote server
nekoconf set cache.ttl 600 --remote-url http://config-server:8000 --remote-api-key "secure-key"
```

See the [CLI Reference](docs/cli-reference.md) for all available commands and options.

## 🔌 Integration Examples

### 🌶️ Flask Integration

```python
from flask import Flask
from nekoconf import NekoConf

app = Flask(__name__)
config_manager = NekoConf("flask_app_config.yaml", event_emission_enabled=True)

# Use configuration values to configure Flask
app.config["DEBUG"] = config_manager.get_bool("app.debug", default=False)
app.config["SECRET_KEY"] = config_manager.get_str("app.secret_key", default="dev-key")

# Listen for configuration changes
@config_manager.on_change("app.*")
def handle_app_config_change(path, new_value, **kwargs):
    if path == "app.debug":
        app.config["DEBUG"] = new_value
    elif path == "app.secret_key":
        app.config["SECRET_KEY"] = new_value
    # Note: Some settings require app restart

@app.route('/')
def index():
    return f"API Version: {config_manager.get('app.version', 'v1.0')}"
```

### ⚡ FastAPI Integration

```python
from fastapi import FastAPI, Depends
from nekoconf import NekoConf

config_manager = NekoConf("fastapi_config.yaml", event_emission_enabled=True)
app = FastAPI(title=config_manager.get("api.title", "My API"))

# Dependency to access configuration
def get_config():
    return config_manager

@app.get("/")
def read_root(config: NekoConf = Depends(get_config)):
    return {"version": config.get("api.version", "1.0")}

# React to configuration changes
@config_manager.on_change("rate_limit.*")
async def update_rate_limits(path, new_value, **kwargs):
    # Update rate limiting middleware configuration
    print(f"Rate limit updated: {path} = {new_value}")
```

### 🎸 Django Integration

```python
# settings.py
from pathlib import Path
from nekoconf import NekoConf

# Initialize configuration
config_manager = NekoConf("django_settings.yaml")

# Use configuration values in Django settings
DEBUG = config_manager.get_bool("django.debug", default=False)
SECRET_KEY = config_manager.get_str("django.secret_key", required=True)
ALLOWED_HOSTS = config_manager.get_list("django.allowed_hosts", default=["localhost"])

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config_manager.get("database.name", "django"),
        'USER': config_manager.get("database.user", "django"),
        'PASSWORD': config_manager.get("database.password", ""),
        'HOST': config_manager.get("database.host", "localhost"),
        'PORT': config_manager.get_int("database.port", 5432),
    }
}

# For dynamic reconfiguration, create an app config to listen for changes
```

### 📱 Microservices Integration with Remote Config

```python
# In your microservice
from nekoconf import NekoConf

# Connect to the central configuration server
config = NekoConf(
    remote_url="http://config-service:8000",
    remote_api_key="service-specific-key",
    in_memory=True,  # No local file needed
    event_emission_enabled=True
)

# Use configuration
service_port = config.get_int("service.port", 8080)
feature_flags = config.get("features", {})

# React to configuration changes in real-time
@config.on_change("features.*")
def handle_feature_change(path, **kwargs):
    print(f"Feature flag changed: {path}")
    # Apply feature change dynamically
```

## 📚 Documentation

NekoConf offers comprehensive documentation for all its core features and advanced usage. For a better experience, each major topic is documented in a dedicated markdown file under the `docs/` directory. See below for quick links and summaries:

| Topic | Description |
|-------|-------------|
| [Environment Variables](docs/environment-variables.md) | How to override config with environment variables, advanced patterns, and customization. |
| [Event System](docs/event-system.md) | Real-time event handling, usage patterns, and best practices. |
| [Web Server & REST API](docs/web-server.md) | Running the FastAPI server, REST API endpoints, Web UI, and security. |
| [CLI Reference](docs/cli-reference.md) | Full command-line usage, options, and examples. |
| [Schema Validation](docs/schema-validation.md) | Using JSON Schema for config validation, error handling, and tips. |
| [Security Considerations](docs/security.md) | API key usage, best practices, and deployment security. |
| [Advanced Usage](docs/advanced-usage.md) | Deep dives: concurrency, integration, dynamic reload, and more. |
| [Remote Configuration](docs/remote-configuration.md) | Connecting to remote NekoConf servers, synchronization, and deployment patterns. |

For installation, quick start, and integration examples, see above sections. For detailed guides, visit the linked docs.

## 👩‍💻 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## ❤️ Discord Community

[![Discord](https://img.shields.io/discord/1365929019714834493)](https://discord.gg/jXAxVPSs7K)

> [!NOTE]
> Need support? Contact [k3scat@gmail.com](mailto:k3scat@gmail.com) or join our discord community at [Nya Foundation](https://discord.gg/jXAxVPSs7K)

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.