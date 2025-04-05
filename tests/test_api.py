"""Tests for the ConfigAPI class."""

import pytest
from pathlib import Path
from unittest.mock import patch

from nekoconf.api import ConfigAPI


class TestConfigAPI:
    """Tests for the ConfigAPI class."""

    def test_initialization(self, config_file, schema_file):
        """Test initializing ConfigAPI with various arguments."""
        # Basic initialization
        api = ConfigAPI(config_file)
        assert api.config_manager.config_path == config_file
        assert api.config_manager.schema_path is None

        # With schema
        api = ConfigAPI(config_file, schema_file)
        assert api.config_manager.config_path == config_file
        assert api.config_manager.schema_path == schema_file

        # With string paths
        api = ConfigAPI(str(config_file), str(schema_file))
        assert api.config_manager.config_path == config_file
        assert api.config_manager.schema_path == schema_file

    @pytest.mark.parametrize(
        "key,expected,default",
        [
            # Basic key retrieval
            ("server.host", "localhost", None),
            ("server.port", 8000, None),
            ("server.debug", True, None),
            # Defaults
            ("server.nonexistent", "default", "default"),
            ("nonexistent.key", 42, 42),
            # Section retrieval
            ("server", {"host": "localhost", "port": 8000, "debug": True}, None),
        ],
    )
    def test_get(self, config_api, sample_config, key, expected, default):
        """Test getting configuration values."""
        if key == "server" and expected is not None:  # Special case for dict comparison
            result = config_api.get(key, default)
            assert result["host"] == expected["host"]
            assert result["port"] == expected["port"]
            assert result["debug"] == expected["debug"]
        else:
            assert config_api.get(key, default) == expected

    @pytest.mark.parametrize(
        "method,key,expected,default",
        [
            # Integer tests
            ("get_int", "server.port", 8000, None),
            ("get_int", "server.nonexistent", 9000, 9000),
            ("get_int", "server.host", None, None),
            ("get_str", "server.host", "localhost", None),
            ("get_str", "server.nonexistent", "default", "default"),
            ("get_bool", "server.debug", True, None),
            ("get_bool", "server.nonexistent", False, False),
            ("get_bool", "server.host", None, None),
        ],
    )
    def test_typed_getters(self, config_api, method, key, expected, default):
        """Test the typed getter methods."""
        getter = getattr(config_api, method)
        assert getter(key, default=default) == expected

    def test_complex_getters(self, config_api, complex_config_file):
        """Test getting complex configuration values."""
        # Create API with complex config
        api = ConfigAPI(complex_config_file)

        # Float values
        value = api.get_float("server.timeout")
        assert value == 30.5
        assert isinstance(value, float)

        # List values
        value = api.get_list("server.features")
        assert value == ["api", "admin", "docs"]
        assert isinstance(value, list)

        # Dict values
        value = api.get_dict("server.settings")
        assert value == {"cache": True, "max_connections": 100}
        assert isinstance(value, dict)

    def test_modification_operations(self, config_api):
        """Test set, delete, and update operations."""
        # Set
        config_api.set("server.host", "127.0.0.1")
        assert config_api.get("server.host") == "127.0.0.1"

        # Set nested
        config_api.set("server.ssl.enabled", True)
        assert config_api.get("server.ssl.enabled") is True

        # Delete
        result = config_api.delete("server.debug")
        assert result is True
        assert config_api.get("server.debug") is None

        # Update
        update_data = {"server": {"port": 9000}, "new_key": "value"}
        config_api.update(update_data)
        assert config_api.get("server.port") == 9000
        assert config_api.get("new_key") == "value"

    def test_observer_management(self, config_api, sync_observer):
        """Test registering and unregistering observer functions."""
        # Register
        config_api.observe(sync_observer)
        assert sync_observer in config_api.config_manager.observers

        # Should be notified on changes
        config_api.set("test.key", "value")
        assert sync_observer.called is True
        assert sync_observer.data["test"]["key"] == "value"

        # Unregister
        config_api.stop_observing(sync_observer)
        assert sync_observer not in config_api.config_manager.observers

    def test_reload(self, config_api, config_file):
        """Test reloading configuration."""
        # Modify in memory
        config_api.set("server.host", "changed.value")
        reloaded = config_api.reload()

        assert reloaded["server"]["host"] == "localhost"  # From file, not memory

    def test_validation(self, config_api_with_schema):
        """Test validation of configuration against schema."""
        # Initially valid
        errors = config_api_with_schema.validate()
        print(errors)
        assert errors == []

        # Make invalid
        config_api_with_schema.set("server.port", "not-an-integer")
        errors = config_api_with_schema.validate()
        assert len(errors) > 0
        assert any("port" in error.lower() for error in errors)
