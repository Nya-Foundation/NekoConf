# Schema Validation in NekoConf

NekoConf supports validating your configuration against a JSON Schema (or YAML/TOML schema) to ensure correctness and prevent runtime errors.

## Why Use Schema Validation?

- Catch missing or invalid config values before they cause problems.
- Enforce types, required fields, and value constraints.
- Get clear error messages for troubleshooting.

## How to Use

1. **Write a schema file** (JSON, YAML, or TOML):

```json
{
  "type": "object",
  "properties": {
    "database": {
      "type": "object",
      "properties": {
        "host": {"type": "string"},
        "port": {"type": "integer", "minimum": 1024}
      },
      "required": ["host", "port"]
    }
  },
  "required": ["database"]
}
```

2. **Initialize NekoConf with the schema:**

```python
from nekoconf import NekoConfigManager
config = NekoConfigManager("config.yaml", schema_path="schema.json")
```

3. **Validate your configuration:**

```python
errors = config.validate()
if errors:
    for error in errors:
        print(f"Validation error: {error}")
else:
    print("Configuration is valid!")
```

Or via CLI:

```bash
nekoconf validate --config config.yaml --schema schema.json
```

## Error Reporting

Validation errors are returned as a list of human-readable messages, e.g.:

```
database.port: 'not-a-port' is not of type 'integer'
database: 'host' is a required property
```

## Tips

- Use `minimum`, `maximum`, `enum`, and other JSON Schema features to enforce constraints.
- You can use YAML or TOML for your schema file as well.
- Validation is available both in code and via the CLI.

[!NOTE]
Schema validation is optional but highly recommended for production deployments.
