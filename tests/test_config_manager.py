"""Tests for the ConfigManager class."""

import asyncio
import pytest
from pathlib import Path

from nekoconf.config_manager import ConfigManager
from tests.test_helpers import wait_for_observers


class TestConfigManagerBase:
    """Base tests for ConfigManager initialization and basic functionality."""

    def test_initialization(self):
        """Test various initialization scenarios."""
        # String path
        path = "examples/sample_config.yaml"
        manager = ConfigManager(path)
        assert isinstance(manager.config_path, Path)
        assert str(manager.config_path) == path
        assert manager.schema_path is None

        # Path object
        path = Path("examples/sample_config.yaml")
        schema_path = Path("examples/sample_schema.json")
        manager = ConfigManager(path, schema_path)
        assert manager.config_path == path
        assert manager.schema_path == schema_path

    def test_load_and_save(self, config_manager, sample_config, config_file):
        """Test loading and saving configuration."""
        # Test loading
        assert config_manager.config_data == sample_config
        loaded_config = config_manager.load()
        assert loaded_config == sample_config

        # Test saving with modifications
        config_manager.set("server.port", 9000)
        config_manager.set("new_setting", "value")
        success = config_manager.save()
        assert success is True

        # Verify file was updated
        new_manager = ConfigManager(config_file)
        new_manager.load()
        assert new_manager.get("server.port") == 9000
        assert new_manager.get("new_setting") == "value"

    def test_get_operations(self, config_manager, sample_config):
        """Test various get operations."""
        # Test getting specific keys
        assert config_manager.get("server.host") == "localhost"
        assert config_manager.get("server.port") == 8000
        assert config_manager.get("server.debug") is True

        # Test getting sections
        assert config_manager.get("server") == sample_config["server"]

        # Test defaults
        assert config_manager.get("nonexistent.key", 42) == 42
        assert config_manager.get("nonexistent.key") is None

        # Test get_all
        assert config_manager.get_all() == sample_config
        # Remove test for get_all with argument as it's not supported

    def test_modification_operations(self, config_manager):
        """Test set, delete, and update operations."""
        # Test set
        config_manager.set("server.host", "127.0.0.1")
        config_manager.set("server.ssl", True)
        assert config_manager.get("server.host") == "127.0.0.1"
        assert config_manager.get("server.ssl") is True

        # Test delete
        success = config_manager.delete("server.debug")
        assert success is True
        assert "debug" not in config_manager.config_data["server"]

        # Test failed delete
        success = config_manager.delete("nonexistent.key")
        assert success is False

        # Test update
        update_data = {
            "server": {"port": 9000},
            "database": {"pool_size": 10},
            "new_section": {"key": "value"},
        }
        config_manager.update(update_data)
        assert config_manager.get("server.port") == 9000
        assert config_manager.get("database.pool_size") == 10
        assert config_manager.get("new_section.key") == "value"


class TestConfigManagerObservers:
    """Tests for the observer functionality of ConfigManager."""

    def test_observer_registration(self, config_manager, sync_observer, async_observer):
        """Test registering and unregistering observers."""
        # Register
        config_manager.register_observer(sync_observer)
        assert sync_observer in config_manager.observers

        config_manager.register_observer(async_observer)
        assert async_observer in config_manager.observers

        # Unregister
        config_manager.unregister_observer(sync_observer)
        assert sync_observer not in config_manager.observers

        config_manager.unregister_observer(async_observer)
        assert async_observer not in config_manager.observers

    @pytest.mark.asyncio
    async def test_observer_notification(self, config_manager, sync_observer, async_observer):
        """Test that observers are notified of configuration changes."""
        # Register both types of observers
        config_manager.register_observer(sync_observer)
        config_manager.register_observer(async_observer)

        # Make changes
        config_manager.set("server.port", 9000)

        # For sync observers, the notification happens immediately
        assert sync_observer.called is True
        assert sync_observer.data["server"]["port"] == 9000

        # For async observers, we need to wait
        await wait_for_observers()
        assert async_observer.called is True
        assert async_observer.data["server"]["port"] == 9000

        # Reset and test with update
        sync_observer.reset()
        async_observer.reset()

        config_manager.update({"database": {"name": "new_db"}})
        assert sync_observer.called is True

        await wait_for_observers()
        assert async_observer.called is True
        assert async_observer.data["database"]["name"] == "new_db"


class TestConfigManagerValidation:
    """Tests for the validation functionality of ConfigManager."""

    def test_validation(self, config_manager_with_schema):
        """Test validation with a schema."""
        # Valid configuration
        errors = config_manager_with_schema.validate()
        assert errors == []

        # Invalid configuration
        config_manager_with_schema.set("server.port", "not-an-integer")
        errors = config_manager_with_schema.validate()
        assert len(errors) > 0
        assert any("port" in error.lower() for error in errors)

    def test_validation_edge_cases(self, config_manager):
        """Test validation edge cases."""
        # No schema
        errors = config_manager.validate()
        assert errors == []

        # Non-existent schema file
        config_manager.schema_path = Path("/nonexistent/schema.json")
        res = config_manager.validate()
        assert res == []  # No schema means no validation errors
