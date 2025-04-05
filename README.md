# NekoConf

[![PyPI version](https://img.shields.io/pypi/v/nekoconf.svg)](https://pypi.org/project/nekoconf/)
[![Python versions](https://img.shields.io/pypi/pyversions/nekoconf.svg)](https://pypi.org/project/nekoconf/)
[![License](https://img.shields.io/github/license/k3scat/nekoconf.svg)](https://github.com/k3scat/nekoconf/blob/main/LICENSE)
[![Code Coverage](https://codecov.io/gh/k3scat/nekoconf/branch/main/graph/badge.svg)](https://codecov.io/gh/k3scat/nekoconf)
[![CI/CD](https://github.com/k3scat/nekoconf/actions/workflows/ci.yml/badge.svg)](https://github.com/k3scat/nekoconf/actions/workflows/ci.yml)

NekoConf is a configuration management system for Python applications that provides a modern web UI, real-time updates, and a simple API for integration.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
  - [Web UI](#web-ui)
  - [Command Line Interface](#command-line-interface)
  - [Python API](#python-api)
- [Advanced Usage](#advanced-usage)
  - [Async Support](#async-support)
  - [Schema Validation](#schema-validation)
  - [Bulk Updates](#bulk-updates)
  - [Framework Integration](#framework-integration)
- [API Reference](#api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Configuration Management**
  - Support for YAML and JSON formats
  - Dot notation access to nested values (e.g., `server.host`)
  - Deep merge updates for nested configurations
  - Schema validation

- **Web UI**
  - Form-based visual editor
  - JSON/YAML editors with syntax highlighting
  - Real-time updates via WebSockets
  - Dark and light theme support

- **Real-time Updates**
  - Observe configuration changes with callbacks
  - Support for both synchronous and asynchronous observers
  - WebSocket-based real-time notifications

- **Developer-Friendly API**
  - Simple Python API for integration
  - Type-safe configuration access
  - Async/await support

## Installation

```bash
pip install nekoconf
```

or with schema validation support

```bash
pip install nekoconf[schema]
```

## Quick Start

### Web UI

Start the web server to manage your configuration through a browser:

```bash
nekoconf server --config config.yaml
```

This starts a web server at http://0.0.0.0:8000 where you can view and edit your configuration.

#### Web UI Screenshots

NekoConf features a modern web interface with both dark and light themes:

##### Dark Theme
![Dark Theme](/images/dark.png)

##### Light Theme
![Light Theme](/images/light.png)

### Command Line Interface

```bash
# View a configuration
nekoconf get --config config.yaml server.host

# Update a value
nekoconf set --config config.yaml server.port 8080

# Delete a value
nekoconf delete --config config.yaml unused.feature

# Import from another file
nekoconf import --config config.yaml other_config.json

# Create a new empty configuration file
nekoconf init --config new_config.yaml

# Validate against a schema
nekoconf validate --config config.yaml --schema schema.json
```

### Python API

```python
from nekoconf import ConfigAPI

# Initialize with your configuration file
config = ConfigAPI("config.yaml")

# Get values with type safety
host = config.get_str("server.host", "localhost")
port = config.get_int("server.port", 8080)
debug = config.get_bool("server.debug", False)

# Update values
config.set("server.host", "127.0.0.1")

# Observe changes
def on_config_change(config_data):
    print("Configuration changed:", config_data)

config.observe(on_config_change)
```

## Advanced Usage

### Async Support

NekoConf supports asynchronous observers for configuration changes:

```python
import asyncio
from nekoconf import ConfigAPI

async def async_observer(config_data):
    print("Configuration changed!")
    await asyncio.sleep(0.1)  # Async processing
    print(f"Processed: {config_data}")

async def main():
    config = ConfigAPI("config.yaml")
    config.observe(async_observer)
    
    # Make a change
    config.set("server.port", 9000)
    
    # Wait for processing
    await asyncio.sleep(0.2)

asyncio.run(main())
```

### Schema Validation

Validate your configuration against a schema:

```python
from nekoconf import ConfigAPI

# Initialize with a schema
config = ConfigAPI("config.yaml", schema_path="schema.json")

# Validate configuration
errors = config.validate()
if errors:
    print("Validation errors:", errors)
```

### Bulk Updates

Update multiple values at once:

```python
from nekoconf import ConfigAPI

config = ConfigAPI("config.yaml")

# Update multiple values with deep merge
config.update({
    "server": {
        "host": "127.0.0.1",
        "port": 9000
    }
})
```

### Framework Integration

#### FastAPI Example

```python
from fastapi import FastAPI, Depends
from nekoconf import ConfigAPI

app = FastAPI()
config = ConfigAPI("config.yaml")

def get_config():
    return config

@app.get("/api/config")
def read_config(config=Depends(get_config)):
    return config.get_all()
```

#### Flask Example

```python
from flask import Flask
from nekoconf import ConfigAPI

app = Flask(__name__)
config = ConfigAPI("config.yaml")

# Update Flask config when NekoConf changes
def sync_flask_config(config_data):
    app.config.update(config_data)

config.observe(sync_flask_config)
```

#### Django Example

```python
from django.apps import AppConfig
from nekoconf import ConfigAPI

class MyAppConfig(AppConfig):
    name = 'myapp'
    
    def ready(self):
        from django.conf import settings
        
        config = ConfigAPI("config.yaml")
        
        # Update Django settings when configuration changes
        def update_settings(config_data):
            for key, value in config_data.items():
                if hasattr(settings, key.upper()):
                    setattr(settings, key.upper(), value)
        
        config.observe(update_settings)
```

## API Reference

### ConfigAPI

The main interface for applications to interact with configuration:

```python
# Core methods
config.get(key, default=None)  # Get any value
config.get_str(key, default=None)  # Get string value
config.get_int(key, default=None)  # Get integer value
config.get_bool(key, default=None)  # Get boolean value
config.get_float(key, default=None)  # Get float value
config.get_dict(key, default=None)  # Get dictionary value
config.get_list(key, default=None)  # Get list value

# Update methods
config.set(key, value)  # Set a value
config.delete(key)  # Delete a value
config.update(data, deep_merge=True)  # Update multiple values

# Observer pattern
config.observe(callback)  # Register change observer
config.stop_observing(callback)  # Remove observer

# Other operations
config.reload()  # Reload from file
config.validate()  # Validate against schema
config.get_all()  # Get entire configuration
```

### ConfigManager

Low-level class for managing configuration files:

```python
manager = ConfigManager("config.yaml")
manager.load()  # Load from file
manager.save()  # Save to file
manager.register_observer(callback)  # Add observer
```

### WebServer

Web server for managing configuration through a UI:

```python
server = WebServer(config_manager)
server.run(host="0.0.0.0", port=8000)
```

## Development

Set up a development environment:

```bash
git clone https://github.com/k3scat/nekoconf.git
cd nekoconf
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
pytest --cov=nekoconf
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.