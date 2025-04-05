"""Tests for the schema validation module."""

import json
import yaml
import pytest
from pathlib import Path

from nekoconf.schema_validator import SchemaValidator


class TestSchemaValidator:
    """Tests for the SchemaValidator class."""

    def test_initialization(self, schema_file, sample_schema):
        """Test initializing the SchemaValidator with various inputs."""
        # Path
        validator = SchemaValidator(schema_file)
        assert validator.schema == sample_schema

        # Dict
        validator = SchemaValidator(sample_schema)
        assert validator.schema == sample_schema

        # String path
        validator = SchemaValidator(str(schema_file))
        assert validator.schema == sample_schema

    def test_validation(self, sample_schema, valid_config, invalid_config):
        """Test validating configurations against schemas."""
        validator = SchemaValidator(sample_schema)

        # Valid config
        errors = validator.validate(valid_config)
        assert errors == [], f"Expected no validation errors, got: {errors}"

        # Invalid config
        errors = validator.validate(invalid_config)

        print(f"Validation errors: {errors}")
        assert len(errors) > 0, "Expected validation errors"

        # Check specific errors
        assert any("port" in error for error in errors), "Should have error about port type"
        assert any("debug" in error for error in errors), "Should have error about debug type"
        assert any(
            "pool_size" in error for error in errors
        ), "Should have error about pool_size minimum"
        assert any("level" in error for error in errors), "Should have error about level enum"

    def test_example_schema_validation(self, example_schema_path, example_config_path):
        """Test validation using example schema and config files."""
        if not example_schema_path or not example_config_path:
            pytest.skip("Example schema or config file not found")

        validator = SchemaValidator(example_schema_path)

        # Load the example config
        with open(example_config_path) as f:
            if example_config_path.suffix in (".yaml", ".yml"):
                config_data = yaml.safe_load(f)
            else:
                config_data = json.load(f)

        # Validate against the example schema
        errors = validator.validate(config_data)

        # The example schema should validate the example config
        assert errors == [], f"Example config validation failed: {errors}"
