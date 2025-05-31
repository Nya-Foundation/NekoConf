"""Tests for the NekoConfig class."""

from pathlib import Path

from nekoconf.core.config import NekoConf


class TestNekoConfigBase:
    """Base tests for NekoConf initialization and basic functionality."""

    def test_load_and_save(
        self,
        config_manager: NekoConf,
        sample_config,
        complex_sample_config,
        config_file,
    ):
        """Test loading and saving configuration."""
        # Test loading
        assert config_manager.data == sample_config
        config_manager.data = complex_sample_config

        success = config_manager.save()
        assert success is True

        loaded_config = config_manager.load()
        assert loaded_config == complex_sample_config

        # Test saving with modifications
        config_manager.set("server.port", 9000)
        config_manager.set("new_setting", "value")

        success = config_manager.save()
        assert success is True

        # Verify file was updated
        new_manager = NekoConf(config_file)

        new_manager.set("server.port", 9000)
        new_manager.set("new_setting", "value")

        assert new_manager.get("server.port") == 9000
        assert new_manager.get("new_setting") == "value"

        new_manager.load()
        assert new_manager.get("server.port") == 8000
        assert new_manager.get("new_setting") == None

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
        config_manager.set("server.host", "0.0.0.0")
        config_manager.set("server.ssl", True)
        assert config_manager.get("server.host") == "0.0.0.0"
        assert config_manager.get("server.ssl") is True

        # Test delete
        success = config_manager.delete("server.debug")
        assert success is True
        assert "debug" not in config_manager.data["server"]

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


class TestNekoConfigValidation:
    """Tests for the validation functionality of NekoConfig."""

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
