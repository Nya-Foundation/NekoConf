# Environment Variable Overrides in NekoConf

NekoConf allows you to override configuration values using environment variables, making it easy to adapt your app to different environments (dev, staging, prod) without changing config files.

## How It Works

- By default, any config key can be overridden by an environment variable.
- The default prefix is `NEKOCONF_` and nested keys use `_` as a delimiter.
- Example: `database.host` → `NEKOCONF_DATABASE_HOST`

| Config Key         | Environment Variable         |
|--------------------|-----------------------------|
| `database.host`    | `NEKOCONF_DATABASE_HOST`    |
| `features.enabled` | `NEKOCONF_FEATURES_ENABLED` |
| `logging.level`    | `NEKOCONF_LOGGING_LEVEL`    |

## Usage Example

```bash
export NEKOCONF_DATABASE_HOST=prod-db.example.com
export NEKOCONF_FEATURES_ENABLED=true
```

```python
from nekoconf import NekoConfigManager
config = NekoConfigManager("config.yaml")
print(config.get("database.host"))  # prod-db.example.com
print(config.get_bool("features.enabled"))  # True
```

## Customizing Prefix and Delimiter

You can change the prefix and delimiter to fit your environment:

```python
config = NekoConfigManager(
    "config.yaml",
    env_prefix="MYAPP",
    env_nested_delimiter="__"
)
```

This maps `database.host` to `MYAPP_DATABASE__HOST`.

## Advanced Options

- **Include/Exclude Paths:** Limit overrides to specific keys.
- **Preserve Case:** Keep original case in env var names.
- **Strict Parsing:** Raise errors if env values can't be parsed.

```python
config = NekoConfigManager(
    "config.yaml",
    env_include_paths=["database", "features.enabled"],
    env_exclude_paths=["logging.secret_key"],
    env_preserve_case=True,
    env_strict_parsing=True
)
```

[!TIP]
Use environment overrides for secrets, credentials, or deployment-specific settings.

## Troubleshooting

- If a value isn't overridden, check the prefix, delimiter, and include/exclude settings.
- Use `config.get("key")` to verify the effective value.

[!NOTE]
Environment overrides are applied on load and can be combined with file-based changes.
