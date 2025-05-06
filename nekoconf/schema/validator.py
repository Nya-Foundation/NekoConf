"""Schema validation for configuration files."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

# These imports should always succeed because this module is only imported
# when HAS_SCHEMA_DEPS is True in __init__.py
import jsonschema
from jsonschema import validators

from ..utils.helper import getLogger

try:
    import tomli  # Python < 3.11
except ImportError:
    try:
        import tomllib as tomli  # Python >= 3.11
    except ImportError:
        tomli = None  # TOML support will be disabled


class NekoSchemaValidator:
    """Validates configuration data against a schema using jsonschema."""

    def __init__(self, schema: Union[Dict[str, Any], str, Path], logger: logging.Logger = None):
        """Initialize the schema validator.

        Args:
            schema: The schema to validate against
            logger: Optional logger instance
        """
        self.logger = logger or getLogger(__name__)

        if isinstance(schema, (str, Path)):
            self.schema = self._load_schema_file(schema)

            if not isinstance(self.schema, dict):
                raise ValueError("Schema file must contain a valid JSON, YAML, or TOML object.")
        elif isinstance(schema, dict):
            self.schema = schema
        else:
            raise TypeError(f"Schema must be a dict, string, or Path, not {type(schema)}")

        # Create a validator with the schema
        self.validator = validators.validator_for(self.schema)(self.schema)

    @classmethod
    def from_file(
        cls, schema_path: Union[str, Path], logger: logging.Logger = None
    ) -> "NekoSchemaValidator":
        """Create a schema validator from a schema file.

        Args:
            schema_path: Path to the schema file (JSON, YAML, or TOML format)
            logger: Optional logger instance

        Returns:
            A NekoValidator instance

        Raises:
            FileNotFoundError: If the schema file doesn't exist
            ValueError: If the file format is unsupported or the file content is invalid
        """
        return cls(schema_path, logger)

    def _load_schema_file(self, schema_path: Union[str, Path]) -> Dict[str, Any]:
        """Load schema from a file.

        Args:
            schema_path: Path to the schema file

        Returns:
            The loaded schema

        Raises:
            FileNotFoundError: If the schema file doesn't exist
            ValueError: If the file format is unsupported or the file content is invalid
        """
        schema_path = Path(schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        file_extension = schema_path.suffix.lower()
        with open(schema_path, "r", encoding="utf-8") as f:
            file_content = f.read()

            if file_extension in (".yaml", ".yml"):
                try:
                    import yaml

                    schema = yaml.safe_load(file_content) or {}
                except ImportError:
                    raise ImportError("YAML support requires 'pyyaml' package.")
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML format in schema file: {e}")
            elif file_extension == ".json":
                try:
                    schema = json.loads(file_content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON format in schema file: {e}")
            elif file_extension == ".toml":
                if tomli is None:
                    raise ImportError(
                        "TOML support requires 'tomli' package for Python < 3.11. "
                        "Install with: pip install tomli"
                    )
                try:
                    schema = tomli.loads(file_content)
                except Exception as e:
                    raise ValueError(f"Invalid TOML format in schema file: {e}")
            else:
                raise ValueError(f"Unsupported file format for schema: {file_extension}")

        return schema

    def validate(self, config_data: Dict[str, Any]) -> List[str]:
        """Validate configuration data against the schema.

        Args:
            config_data: The configuration data to validate

        Returns:
            List of validation errors (empty if validation passed)
        """
        errors = []

        # Create a validator with format checking enabled
        format_validator = jsonschema.validators.validator_for(self.schema)(
            self.schema, format_checker=jsonschema.FormatChecker()
        )

        # Use iter_errors to get all validation errors including format validation
        for error in format_validator.iter_errors(config_data):
            # Format the error path
            path = ".".join(str(part) for part in error.path) if error.path else "Root"
            message = f"{path}: {error.message}"
            errors.append(message)

            # Process sub-errors if present
            if hasattr(error, "context") and error.context:
                for suberror in error.context:
                    subpath = (
                        ".".join(str(part) for part in suberror.path) if suberror.path else "Root"
                    )
                    errors.append(f"{subpath}: {suberror.message}")

        return errors
