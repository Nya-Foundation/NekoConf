"""Unit tests for TOML file format support."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from nekoconf.core.config import NekoConf
from nekoconf.utils.helper import load_file, save_file

# Skip tests if tomli/tomli_w packages are not available
try:
    import tomli

    has_tomli = True
except ImportError:
    try:
        import tomllib as tomli

        has_tomli = True
    except ImportError:
        has_tomli = False

try:
    import tomli_w

    has_tomli_w = True
except ImportError:
    has_tomli_w = False

# This decorator will skip tests if the required packages are not available
requires_toml = pytest.mark.skipif(
    not has_tomli or not has_tomli_w,
    reason="TOML support requires tomli (or Python 3.11+) and tomli_w packages",
)


class TestTomlSupport:
    """Test case for TOML file format support."""

    def setup_method(self):
        """Set up test environment before each test method."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.toml_path = os.path.join(self.temp_dir, "config.toml")

    def teardown_method(self):
        """Clean up after each test method."""
        # Use shutil.rmtree to recursively remove the directory and all its contents
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary directory: {e}")

    @requires_toml
    def test_load_toml_file(self):
        """Test loading configuration from a TOML file."""
        # Create a TOML file
        with open(self.toml_path, "w") as f:
            f.write(
                """
            # This is a TOML document

            title = "TOML Example"
            
            [server]
            host = "localhost"
            port = 8000
            debug = true
            
            [database]
            url = "sqlite:///data.db"
            pool_size = 5
            
            [logging]
            level = "INFO"
            
            [[items]]
            name = "item1"
            value = 42
            
            [[items]]
            name = "item2"
            value = 73
            """
            )

        # Load the file
        config = NekoConf(self.toml_path)
        config.load()

        # Check the values
        assert config.get("title") == "TOML Example"
        assert config.get("server.host") == "localhost"
        assert config.get("server.port") == 8000
        assert config.get("server.debug") == True
        assert config.get("database.url") == "sqlite:///data.db"
        assert config.get("database.pool_size") == 5
        assert config.get("logging.level") == "INFO"
        assert len(config.get("items")) == 2
        assert config.get("items")[0]["name"] == "item1"
        assert config.get("items")[1]["value"] == 73

    @requires_toml
    def test_save_toml_file(self):
        """Test saving configuration to a TOML file."""
        # Create a configuration
        config = NekoConf(self.toml_path)
        config.set("title", "TOML Test")
        config.set("server.host", "0.0.0.0")
        config.set("server.port", 9000)
        config.set("database.url", "postgresql://user:pass@localhost/db")
        config.set("nested.deep.value", 42)
        config.set("array", [1, 2, 3])

        # Save the file
        assert config.save() == True

        # Check that the file exists
        assert os.path.exists(self.toml_path)

        # Load the file directly to verify contents
        data = None
        with open(self.toml_path, "rb") as f:
            data = tomli.load(f)

        # Check the values
        assert data["title"] == "TOML Test"
        assert data["server"]["host"] == "0.0.0.0"
        assert data["server"]["port"] == 9000
        assert data["database"]["url"] == "postgresql://user:pass@localhost/db"
        assert data["nested"]["deep"]["value"] == 42
        assert data["array"] == [1, 2, 3]

    @requires_toml
    def test_toml_load_save_roundtrip(self):
        """Test that loading and saving a TOML file preserves the data."""
        original_data = {
            "title": "TOML Roundtrip",
            "server": {"host": "localhost", "port": 8000, "debug": True},
            "database": {
                "credentials": {"user": "admin", "password": "secret"},
                "settings": {"pool_size": 10, "timeout": 30},
            },
            "values": [{"name": "first", "value": 1}, {"name": "second", "value": 2}],
        }

        # Save the original data
        save_file(self.toml_path, original_data)

        # Load the data
        loaded_data = load_file(self.toml_path)

        # Compare
        assert loaded_data == original_data

    @requires_toml
    def test_client_toml_support(self):
        """Test NekoConf with TOML files."""
        # Create a client with a TOML file
        client = NekoConf(self.toml_path)

        # Set some values
        client.set("server.host", "example.com")
        client.set("server.port", 443)
        client.set("logging.level", "DEBUG")
        client.set("feature_flags.enable_cache", True)

        client.save()

        # Reload the client from file to ensure it saves properly
        client.reload()

        # Check values
        assert client.get_str("server.host") == "example.com"
        assert client.get_int("server.port") == 443
        assert client.get_str("logging.level") == "DEBUG"
        assert client.get_bool("feature_flags.enable_cache") == True

    @requires_toml
    def test_toml_schema_validation(self):
        """Test schema validation with TOML files."""
        # Create a schema file (in TOML format)
        schema_path = os.path.join(self.temp_dir, "schema.toml")

        with open(schema_path, "w") as f:
            f.write(
                """
            # Schema for config validation
            
            [properties.server]
            type = "object"
            
            [properties.server.properties]
            
            [properties.server.properties.host]
            type = "string"
            
            [properties.server.properties.port]
            type = "integer"
            minimum = 1
            maximum = 65535
            
            [properties.logging]
            type = "object"
            
            [properties.logging.properties]
            
            [properties.logging.properties.level]
            type = "string"
            enum = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            
            required = ["server", "logging"]
            """
            )

        # Create a valid configuration
        config = NekoConf(self.toml_path, schema_path)
        config.set("server.host", "localhost")
        config.set("server.port", 8080)
        config.set("logging.level", "INFO")

        # Validate
        errors = config.validate()
        print(errors)  # For debugging purposes
        assert len(errors) == 0

        # Create an invalid configuration
        config.set("server.port", 70000)  # Port exceeds maximum
        config.set("logging.level", "TRACE")  # Not in enum

        # Validate
        errors = config.validate()
        assert len(errors) == 2

    @requires_toml
    def test_toml_mixed_with_other_formats(self):
        """Test that we can work with TOML alongside other formats."""
        # Create files with different formats but same content
        toml_path = os.path.join(self.temp_dir, "config.toml")
        yaml_path = os.path.join(self.temp_dir, "config.yaml")
        json_path = os.path.join(self.temp_dir, "config.json")

        test_data = {
            "server": {"host": "localhost", "port": 8000},
            "database": {"url": "sqlite:///data.db"},
        }

        # Save in each format
        save_file(toml_path, test_data)
        save_file(yaml_path, test_data)
        save_file(json_path, test_data)

        # Load from each format
        toml_data = load_file(toml_path)
        yaml_data = load_file(yaml_path)
        json_data = load_file(json_path)

        # Compare
        assert toml_data == yaml_data == json_data == test_data

        # Cleanup
        for path in [yaml_path, json_path]:
            if os.path.exists(path):
                os.unlink(path)
