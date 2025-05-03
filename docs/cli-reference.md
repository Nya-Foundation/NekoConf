# NekoConf CLI Reference

NekoConf provides a command-line interface (CLI) for managing configuration files, running the web server, and performing validation and import/export operations.

## Basic Usage

```bash
nekoconf --help
```

## Commands Overview

| Command      | Description                                 |
|--------------|---------------------------------------------|
| `server`     | Start the web server and UI                 |
| `get`        | Get a configuration value                   |
| `set`        | Set a configuration value                   |
| `delete`     | Delete a configuration value                |
| `import`     | Import configuration from a file            |
| `validate`   | Validate configuration against a schema     |
| `init`       | Create a new empty configuration file       |

## Command Details & Examples

### Start the Web Server

```bash
nekoconf server --config config.yaml --port 8000 --api-key mykey
```

### Get a Value

```bash
nekoconf get database.host --config config.yaml
nekoconf get --config config.yaml --format json
```

### Set a Value

```bash
nekoconf set database.port 5432 --config config.yaml
```

### Delete a Value

```bash
nekoconf delete old.setting --config config.yaml
```

### Import Configuration

```bash
nekoconf import import.yaml --config config.yaml
```

### Validate Configuration

```bash
nekoconf validate --config config.yaml --schema schema.json
```

### Create a New Config File

```bash
nekoconf init --config new.yaml
```

## Options

- `--config, -c` : Path to the configuration file (YAML, JSON, TOML)
- `--schema`     : Path to a schema file for validation
- `--api-key`    : API key for securing the server
- `--read-only`  : Start server in read-only mode
- `--reload`     : Enable auto-reload for development
- `--format, -f` : Output format for `get` (raw, json, yaml)

[!TIP]
Use `--debug` for verbose output and troubleshooting.

[!NOTE]
All commands support YAML, JSON, and TOML files.
