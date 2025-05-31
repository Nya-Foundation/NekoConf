"""Integration tests for NekoConf components working together."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from nekoconf.core.config import NekoConf
from nekoconf.event.type import EventType


class TestNekoConfIntegration:
    """Integration tests for NekoConf with events and transactions."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary configuration file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            # Initial configuration
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {"username": "admin", "password": "secret"},
                },
                "logging": {"level": "INFO", "format": "%(asctime)s - %(levelname)s - %(message)s"},
                "features": {"dark_mode": False, "notifications": True},
            }
            tmp_path = Path(tmp.name)

        # Write config to file outside the with block
        with open(tmp_path, "w") as f:
            yaml.dump(config, f)

        yield tmp_path

        # Cleanup
        if tmp_path.exists():
            os.unlink(tmp_path)

    def test_load_and_modify(self, temp_config_file):
        """Test loading from file and modifying configuration."""
        manager = NekoConf(temp_config_file, event_emission_enabled=True)

        # Verify initial state
        assert manager.get("database.host") == "localhost"
        assert manager.get("database.port") == 5432

        # Modify and save
        manager.set("database.host", "db.example.com")
        manager.save()

        # Create a new instance to verify persistence
        new_manager = NekoConf(temp_config_file)
        assert new_manager.get("database.host") == "db.example.com"
        assert new_manager.get("database.port") == 5432

    def test_transaction_commit(self, temp_config_file):
        """Test transaction commit functionality."""
        manager = NekoConf(temp_config_file, event_emission_enabled=True)

        # Set up event handler to track changes
        event_handler = MagicMock()
        event_handler.__name__ = "mock_event_handler"
        manager.on_event(EventType.CHANGE)(event_handler)

        # Use transaction
        with manager.transaction() as txn:
            txn.set("database.host", "db.example.com")
            txn.set("database.port", 3306)
            txn.delete("features.dark_mode")
            txn.set("new.key", "value")

        # Verify changes were applied
        assert manager.get("database.host") == "db.example.com"
        assert manager.get("database.port") == 3306
        assert "dark_mode" not in manager.get("features")
        assert manager.get("new.key") == "value"

        # Verify events were emitted (should include multiple calls)
        assert event_handler.call_count >= 1

        # Verify persistence
        new_manager = NekoConf(temp_config_file)
        assert new_manager.get("database.host") == "db.example.com"
        assert new_manager.get("new.key") == "value"

    def test_event_handling(self, temp_config_file):
        """Test event handling functionality."""
        manager = NekoConf(temp_config_file, event_emission_enabled=True)

        # Set up event handlers
        db_handler = MagicMock()
        log_handler = MagicMock()
        global_handler = MagicMock()

        db_handler.__name__ = "db_event_handler"
        log_handler.__name__ = "log_event_handler"
        global_handler.__name__ = "global_event_handler"

        # Register handlers
        manager.on_change("database.*")(db_handler)
        manager.on_change("logging.*")(log_handler)
        manager.on_change("@global")(global_handler)

        # Make changes
        manager.set("database.host", "db.example.com")
        manager.set("logging.level", "DEBUG")

        # Verify correct handlers were called
        assert db_handler.call_count == 1
        assert log_handler.call_count == 1
        assert global_handler.call_count == 2  # Called for both changes

        # Reset mocks
        db_handler.reset_mock()
        log_handler.reset_mock()
        global_handler.reset_mock()

        # Update multiple values at once
        manager.update({"database": {"port": 3306}, "logging": {"format": "simple"}})

        # Both handlers should be called once for their respective paths
        assert db_handler.call_count >= 1
        assert log_handler.call_count >= 1
        assert global_handler.call_count >= 1

    def test_path_pattern_matching(self, temp_config_file):
        """Test path pattern matching for event handlers."""
        manager = NekoConf(temp_config_file, event_emission_enabled=True)

        # Set up handlers with different path patterns
        exact_handler = MagicMock()
        wildcard_handler = MagicMock()
        nested_wildcard_handler = MagicMock()

        exact_handler.__name__ = "exact_event_handler"
        wildcard_handler.__name__ = "wildcard_event_handler"
        nested_wildcard_handler.__name__ = "nested_wildcard_event_handler"

        # Register handlers
        manager.on_change("database.host")(exact_handler)
        manager.on_change("database.*")(wildcard_handler)
        manager.on_change("database.*.username")(nested_wildcard_handler)

        # Make changes that should trigger specific handlers
        manager.set("database.host", "db.example.com")

        # Verify handlers were called correctly
        assert exact_handler.call_count == 1
        assert wildcard_handler.call_count == 1
        assert nested_wildcard_handler.call_count == 0

        # Reset mocks
        exact_handler.reset_mock()
        wildcard_handler.reset_mock()
        nested_wildcard_handler.reset_mock()

        # Make a change that should trigger the nested wildcard handler
        manager.set("database.credentials.username", "newuser")

        assert exact_handler.call_count == 0
        assert wildcard_handler.call_count == 1
        assert nested_wildcard_handler.call_count == 1

    def test_event_disabled(self, temp_config_file):
        """Test that events can be disabled."""
        # Create manager with events disabled
        manager = NekoConf(temp_config_file, event_emission_enabled=False)

        # Set up handlers
        handler = MagicMock()
        handler.__name__ = "disabled_event_handler"
        manager.on_change("*")(handler)

        # Make changes
        manager.set("database.host", "db.example.com")
        manager.update({"logging": {"level": "DEBUG"}})

        # Verify no events were emitted
        assert handler.call_count == 0

    def test_environment_overrides(self, temp_config_file):
        """Test environment variable overrides."""
        # Set environment variables

        os.environ["NEKOCONF_DATABASE_HOST"] = "env-host"
        os.environ["NEKOCONF_LOGGING_LEVEL"] = "DEBUG"

        # Create manager with env overrides enabled
        manager = NekoConf(temp_config_file, env_override_enabled=True, event_emission_enabled=True)
        manager.load()

        # Verify environment overrides are applied
        assert manager.get("database.host") == "env-host"
        assert manager.get("logging.level") == "DEBUG"

        # Set up event handler
        handler = MagicMock()
        handler.__name__ = "env_event_handler"
        manager.on_change("database.host")(handler)

        # Change value that was overridden
        manager.set("database.host", "new-host")

        # Verify event was emitted for the change
        assert handler.call_count == 1

        # Environment override should be overridden by set()
        assert manager.get("database.host") == "new-host"

        # Save and reload to verify persistence
        manager.save()

        # Create new manager - should still have env overrides
        new_manager = NekoConf(temp_config_file, env_override_enabled=True)
        new_manager.reload()

        # Env vars should still take precedence over saved values
        assert new_manager.get("database.host") == "env-host"

        # But if we disable env overrides, should get file value
        no_env_manager = NekoConf(temp_config_file, env_override_enabled=False)

        assert no_env_manager.get("database.host") == "new-host"
