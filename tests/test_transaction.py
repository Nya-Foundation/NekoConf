"""Test cases for the TransactionManager class."""

import copy
from unittest.mock import MagicMock, patch

import pytest

from nekoconf.core.config import NekoConf
from nekoconf.event.transaction import TransactionManager


class TestTransactionManager:
    """Test cases for TransactionManager functionality."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager for testing."""
        config = MagicMock(spec=NekoConf)
        config.data = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "secret"},
            },
            "logging": {"level": "INFO", "format": "%(asctime)s - %(levelname)s - %(message)s"},
            "features": {"dark_mode": False, "notifications": True},
        }
        config.event_disabled = False
        # Add event_pipeline attribute for emit_change_events to work
        config.event_pipeline = MagicMock()
        return config

    def test_transaction_initialization(self, mock_config_manager):
        """Test transaction initialization."""
        transaction = TransactionManager(mock_config_manager)

        # Transaction should have a copy of the original data
        assert transaction.transaction_data == mock_config_manager.data
        assert transaction.transaction_data is not mock_config_manager.data  # Deep copy
        assert transaction.old_data == mock_config_manager.data

    def test_transaction_get(self, mock_config_manager):
        """Test getting values from a transaction."""
        transaction = TransactionManager(mock_config_manager)

        # Test getting entire configuration
        assert transaction.get() == mock_config_manager.data

        # Test getting specific values
        assert transaction.get("database.host") == "localhost"
        assert transaction.get("database.port") == 5432
        assert transaction.get("database.credentials.username") == "admin"

        # Test getting with default value
        assert transaction.get("database.timeout", 30) == 30
        assert transaction.get("nonexistent.key", "default") == "default"

    def test_transaction_set(self, mock_config_manager):
        """Test setting values in a transaction."""
        transaction = TransactionManager(mock_config_manager)

        # Set simple values
        transaction.set("database.host", "db.example.com")
        transaction.set("database.port", 3306)

        # Check that values were updated in transaction data
        assert transaction.get("database.host") == "db.example.com"
        assert transaction.get("database.port") == 3306

        # Set nested value
        transaction.set("database.credentials.username", "newuser")
        assert transaction.get("database.credentials.username") == "newuser"

        # Set new value
        transaction.set("cache.ttl", 300)
        assert transaction.get("cache.ttl") == 300

        # Original config should be unchanged
        assert mock_config_manager.data["database"]["host"] == "localhost"
        assert mock_config_manager.data["database"]["port"] == 5432

    def test_transaction_delete(self, mock_config_manager):
        """Test deleting values in a transaction."""
        transaction = TransactionManager(mock_config_manager)

        # Delete existing key
        result = transaction.delete("database.credentials.password")
        assert result is True
        assert transaction.get("database.credentials.password", None) is None
        assert "password" not in transaction.get("database.credentials")

        # Delete non-existent key
        result = transaction.delete("database.nonexistent")
        assert result is False

        # Original config should be unchanged
        assert mock_config_manager.data["database"]["credentials"]["password"] == "secret"

    def test_transaction_update(self, mock_config_manager):
        """Test updating multiple values in a transaction."""
        transaction = TransactionManager(mock_config_manager)

        # Update multiple values at once
        transaction.update(
            {
                "database": {"host": "db.example.com", "pool_size": 10},  # New key
                "logging": {"level": "DEBUG"},
            }
        )

        # Check that values were updated
        assert transaction.get("database.host") == "db.example.com"
        assert transaction.get("database.pool_size") == 10
        assert transaction.get("logging.level") == "DEBUG"

        # Check that other values remain unchanged
        assert transaction.get("database.port") == 5432
        assert transaction.get("database.credentials.username") == "admin"

        # Original config should be unchanged
        assert mock_config_manager.data["database"]["host"] == "localhost"
        assert "pool_size" not in mock_config_manager.data["database"]

    def test_transaction_replace(self, mock_config_manager):
        """Test replacing the entire configuration in a transaction."""
        transaction = TransactionManager(mock_config_manager)

        new_config = {
            "app": {"name": "MyApp", "version": "1.0.0"},
            "server": {"host": "0.0.0.0", "port": 8080},
        }

        # Replace entire configuration
        transaction.replace(new_config)

        # New values should be accessible
        assert transaction.get("app.name") == "MyApp"
        assert transaction.get("server.port") == 8080

        # Old values should be gone
        assert transaction.get("database", None) is None
        assert transaction.get("logging", None) is None

        # Original config should be unchanged
        assert "database" in mock_config_manager.data
        assert "app" not in mock_config_manager.data

    @patch("nekoconf.event.changes.emit_change_events")
    def test_transaction_commit(self, mock_emit_events, mock_config_manager):
        """Test committing a transaction to the configuration manager."""
        transaction = TransactionManager(mock_config_manager)

        # Make some changes
        transaction.set("database.host", "db.example.com")
        transaction.set("database.port", 3306)
        transaction.delete("features.dark_mode")
        transaction.set("new.key", "value")

        # Commit changes
        changes = transaction.commit()

        # Changes should be applied to config manager
        assert mock_config_manager.data["database"]["host"] == "db.example.com"
        assert mock_config_manager.data["database"]["port"] == 3306
        assert "dark_mode" not in mock_config_manager.data["features"]
        assert mock_config_manager.data["new"]["key"] == "value"

        # # Events should be emitted
        # assert mock_emit_events.called
        # mock_emit_events.assert_called_once_with(mock_config_manager, changes)

        # # Check that changes list contains expected changes
        assert len(changes) > 0

    def test_transaction_commit_with_disabled_events(self, mock_config_manager):
        """Test committing a transaction with events disabled."""
        mock_config_manager.event_disabled = True
        transaction = TransactionManager(mock_config_manager)

        # Make some changes
        transaction.set("database.host", "db.example.com")

        with patch("nekoconf.event.changes.emit_change_events") as mock_emit_events:
            transaction.commit()

            # Events should not be emitted
            assert not mock_emit_events.called
