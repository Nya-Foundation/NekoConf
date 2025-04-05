"""Schema validation for configuration files."""

import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Union

import jsonschema
from jsonschema import validators


class SchemaValidator:
    """Validates configuration data against a schema using jsonschema."""

    def __init__(self, schema: Union[Dict[str, Any], str, Path]):
        """Initialize the schema validator.

        Args:
            schema: The schema to validate against
        """
        if isinstance(schema, (str, Path)):
            self.schema = self._load_schema_file(schema)

            if not isinstance(self.schema, dict):
                raise ValueError("Schema file must contain a valid JSON or YAML object.")
        elif isinstance(schema, dict):
            self.schema = schema

        # Create a validator with the schema
        self.validator = validators.validator_for(self.schema)(self.schema)

    @classmethod
    def from_file(cls, schema_path: Union[str, Path]) -> "SchemaValidator":
        """Create a schema validator from a schema file.

        Args:
            schema_path: Path to the schema file (JSON or YAML format)

        Returns:
            A SchemaValidator instance

        Raises:
            FileNotFoundError: If the schema file doesn't exist
            ValueError: If the file format is unsupported or the file content is invalid
        """
        return cls(schema_path)

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
                    schema = yaml.safe_load(file_content) or {}
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML format in schema file: {e}")
            elif file_extension == ".json":
                try:
                    schema = json.loads(file_content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON format in schema file: {e}")
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

        # Use iter_errors to get all validation errors rather than stopping at the first one
        for error in self.validator.iter_errors(config_data):
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

        # Check for format errors using the validator's FORMAT_CHECKER
        validator_class = jsonschema.validators.validator_for(self.schema)
        format_checker = validator_class.FORMAT_CHECKER
        format_validator = validator_class(self.schema, format_checker=format_checker)

        for error in format_validator.iter_errors(config_data):
            # Only add if it's a new error (format validation)
            path = ".".join(str(part) for part in error.path) if error.path else "Root"
            message = f"{path}: {error.message}"
            if message not in errors:
                errors.append(message)

        return errors
