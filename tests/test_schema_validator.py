"""Tests for the schema validation module.

This module provides comprehensive test coverage for NekoConf's schema validation
functionality, including validation against various schema formats, error handling,
and different initialization methods.
"""

import json

import pytest
import yaml

from nekoconf.schema import NekoSchemaValidator


class TestNekoSchemaValidator:
    """Test suite for the NekoSchemaValidator class.

    This test suite verifies that the schema validator:
    - Can be initialized with different input types (dict, path, string)
    - Correctly validates configurations against schemas
    - Handles validation errors appropriately
    - Processes different file formats (JSON, YAML)
    - Reports useful error messages for schema violations
    """

    def test_initialization_with_dict(self, sample_schema):
        """Test initializing the validator with a schema dictionary."""
        validator = NekoSchemaValidator(sample_schema)
        assert validator.schema == sample_schema
        assert validator.validator is not None

    def test_initialization_with_path(self, schema_file, sample_schema):
        """Test initializing the validator with a Path object."""
        validator = NekoSchemaValidator(schema_file)
        assert validator.schema == sample_schema
        assert validator.validator is not None

    def test_initialization_with_string_path(self, schema_file, sample_schema):
        """Test initializing the validator with a string path."""
        validator = NekoSchemaValidator(str(schema_file))
        assert validator.schema == sample_schema
        assert validator.validator is not None

    def test_from_file_factory_method(self, schema_file, sample_schema):
        """Test the from_file class factory method."""
        validator = NekoSchemaValidator.from_file(schema_file)
        assert validator.schema == sample_schema
        assert validator.validator is not None

    def test_initialization_with_invalid_type(self):
        """Test initializing with invalid schema type raises appropriate error."""
        with pytest.raises(TypeError, match="Schema must be a dict, string, or Path"):
            NekoSchemaValidator([1, 2, 3])  # List is invalid type

    def test_empty_schema_validation(self):
        """Test validation with empty schema."""
        validator = NekoSchemaValidator({})
        # Empty schema should validate any object
        assert validator.validate({"any": "data"}) == []
        assert validator.validate([1, 2, 3]) == []

    def test_basic_validation(self, sample_schema, valid_config):
        """Test validation with valid configuration."""
        validator = NekoSchemaValidator(sample_schema)
        errors = validator.validate(valid_config)
        assert errors == [], f"Expected no validation errors, got: {errors}"

    def test_validation_errors(self, sample_schema, invalid_config):
        """Test validation with invalid configuration returns appropriate errors."""
        validator = NekoSchemaValidator(sample_schema)
        errors = validator.validate(invalid_config)

        # Should have errors
        assert len(errors) > 0, "Expected validation errors"

        # Check specific error messages
        error_text = "\n".join(errors)
        assert "port" in error_text, "Should have error about port type"
        assert "debug" in error_text, "Should have error about debug type"
        assert "pool_size" in error_text, "Should have error about pool_size minimum"
        assert "level" in error_text, "Should have error about level enum"

    def test_format_validation(self, tmp_path):
        """Test format validation in JSON Schema."""
        # Create schema with format validation
        schema = {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "date": {"type": "string", "format": "date"},
                "uri": {"type": "string", "format": "uri"},
            },
        }

        validator = NekoSchemaValidator(schema)

        # Test with valid formats
        valid_data = {
            "email": "user@example.com",
            "date": "2023-12-25",
            "uri": "https://example.com",
        }
        errors = validator.validate(valid_data)
        assert errors == [], f"Expected no validation errors, got: {errors}"

        # Test with invalid formats
        invalid_data = {
            "email": "not-an-email",
            "date": "not-a-date",
            "uri": "123not-a-uri",
        }
        errors = validator.validate(invalid_data)
        assert len(errors) == 3, f"Expected 3 validation errors, got: {len(errors)}"
        assert any("email" in e for e in errors), "Should have error about email format"
        assert any("date" in e for e in errors), "Should have error about date format"
        assert any("uri" in e for e in errors), "Should have error about uri format"

    def test_load_schema_file_yaml(self, tmp_path):
        """Test loading schema from YAML file."""
        # Create a test YAML schema file
        schema_path = tmp_path / "schema.yaml"
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }

        with open(schema_path, "w") as f:
            yaml.dump(schema, f)

        # Load the schema file
        validator = NekoSchemaValidator(schema_path)

        # Validate the schema was loaded correctly
        assert validator.schema == schema

        # Test validation with the schema
        assert validator.validate({"name": "John", "age": 30}) == []
        errors = validator.validate({"age": "thirty"})
        assert len(errors) > 0, "Expected validation errors"

    def test_load_schema_file_json(self, tmp_path):
        """Test loading schema from JSON file."""
        # Create a test JSON schema file
        schema_path = tmp_path / "schema.json"
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name"],
        }

        with open(schema_path, "w") as f:
            json.dump(schema, f)

        # Load the schema file
        validator = NekoSchemaValidator(schema_path)

        # Validate the schema was loaded correctly
        assert validator.schema == schema

        # Test validation with the schema
        assert validator.validate({"name": "John", "age": 30}) == []
        errors = validator.validate({"age": "thirty"})
        assert len(errors) > 0, "Expected validation errors"

    def test_load_schema_file_toml(self, tmp_path):
        """Test loading schema from TOML file if tomli is available."""
        try:
            import tomli  # Try to import tomli
            import tomli_w  # Try to import tomli-w

            # Create a test TOML schema file
            schema_path = tmp_path / "schema.toml"
            schema = {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name"],
            }

            with open(schema_path, "wb") as f:
                tomli_w.dump(schema, f)

            # Load the schema file
            validator = NekoSchemaValidator(schema_path)

            # Validate the schema was loaded correctly
            assert validator.schema == schema

            # Test validation with the schema
            assert validator.validate({"name": "John", "age": 30}) == []
            errors = validator.validate({"age": "thirty"})
            assert len(errors) > 0, "Expected validation errors"

        except (ImportError, FileNotFoundError):
            pytest.skip("TOML support not available")

    def test_file_not_found(self):
        """Test FileNotFoundError is raised for non-existent schema file."""
        with pytest.raises(FileNotFoundError):
            NekoSchemaValidator("/path/to/nonexistent/schema.json")

    def test_invalid_schema_format(self, tmp_path):
        """Test ValueError is raised for invalid schema format."""
        # Create an invalid YAML file
        invalid_schema = tmp_path / "invalid.yaml"
        with open(invalid_schema, "w") as f:
            f.write("invalid: yaml: : content : :")

        with pytest.raises(ValueError, match="Invalid YAML format"):
            NekoSchemaValidator(invalid_schema)

    def test_unsupported_file_format(self, tmp_path):
        """Test ValueError is raised for unsupported file format."""
        # Create a file with unsupported extension
        unsupported = tmp_path / "schema.txt"
        with open(unsupported, "w") as f:
            f.write('{"type": "object"}')

        with pytest.raises(ValueError, match="Unsupported file format"):
            NekoSchemaValidator(unsupported)

    def test_validation_with_complex_schema(self, tmp_path):
        """Test validation with a complex schema with nested objects, arrays, etc."""
        complex_schema = {
            "type": "object",
            "properties": {
                "server": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "flags": {"type": "array", "items": {"type": "string"}},
                        "settings": {
                            "type": "object",
                            "properties": {
                                "timeout": {"type": "number"},
                                "retries": {"type": "integer"},
                            },
                            "required": ["timeout"],
                        },
                    },
                    "required": ["host", "port"],
                },
                "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
            },
            "required": ["server", "version"],
        }

        validator = NekoSchemaValidator(complex_schema)

        # Valid complex data
        valid_complex = {
            "server": {
                "host": "example.com",
                "port": 8080,
                "flags": ["secure", "fast"],
                "settings": {"timeout": 30.5, "retries": 3},
            },
            "version": "1.2.3",
        }
        errors = validator.validate(valid_complex)
        assert errors == [], f"Expected no validation errors, got: {errors}"

        # Invalid complex data with multiple issues
        invalid_complex = {
            "server": {
                "host": 123,  # Should be string
                "port": 70000,  # Exceeds maximum
                "flags": "not-an-array",  # Should be array
                "settings": {
                    # Missing required timeout
                    "retries": "three"  # Should be integer
                },
            },
            "version": "1.2",  # Doesn't match pattern
        }

        errors = validator.validate(invalid_complex)
        assert len(errors) >= 5, f"Expected at least 5 validation errors, got: {len(errors)}"

    def test_example_schema_validation(self, example_schema_path, example_config_path):
        """Test validation using example schema and config files from fixtures."""
        if not example_schema_path or not example_config_path:
            pytest.skip("Example schema or config file not found")

        validator = NekoSchemaValidator(example_schema_path)

        # Load the example config
        with open(example_config_path) as f:
            if str(example_config_path).endswith((".yaml", ".yml")):
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)

        # Validate against the example schema
        errors = validator.validate(config_data)
        assert errors == [], f"Example config validation failed: {errors}"
