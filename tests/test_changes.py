"""Test cases for change detection and tracking."""

import pytest

from nekoconf.event.changes import ChangeTracker, ChangeType, ConfigChange


class TestConfigChange:
    """Test cases for ConfigChange class."""

    def test_config_change_initialization(self):
        """Test ConfigChange initialization."""
        change = ConfigChange(
            change_type=ChangeType.UPDATE,
            path="database.host",
            old_value="localhost",
            new_value="db.example.com",
        )

        assert change.change_type == ChangeType.UPDATE
        assert change.path == "database.host"
        assert change.old_value == "localhost"
        assert change.new_value == "db.example.com"

    def test_to_event_type(self):
        """Test conversion of ChangeType to EventType."""
        from nekoconf.event.type import EventType

        # Test CREATE mapping
        change = ConfigChange(ChangeType.CREATE)
        assert change.to_event_type() == EventType.CREATE

        # Test UPDATE mapping
        change = ConfigChange(ChangeType.UPDATE)
        assert change.to_event_type() == EventType.UPDATE

        # Test DELETE mapping
        change = ConfigChange(ChangeType.DELETE)
        assert change.to_event_type() == EventType.DELETE

        # Test CHANGE mapping
        change = ConfigChange(ChangeType.CHANGE)
        assert change.to_event_type() == EventType.CHANGE


class TestChangeTracker:
    """Test cases for ChangeTracker functionality."""

    def test_detect_changes_create(self):
        """Test detecting a create change."""
        old_config = {"database": {"port": 5432}}
        new_config = {"database": {"port": 5432, "host": "localhost"}}

        change = ChangeTracker.detect_changes(old_config, new_config)[1]

        assert change is not None
        assert change.change_type == ChangeType.CREATE
        assert change.path == "database.host"
        assert change.old_value is None
        assert change.new_value == "localhost"

    def test_detect_changes_update(self):
        """Test detecting an update change."""
        old_config = {"database": {"host": "localhost"}}
        new_config = {"database": {"host": "db.example.com"}}

        change = ChangeTracker.detect_changes(old_config, new_config)[1]

        assert change is not None
        assert change.change_type == ChangeType.UPDATE
        assert change.path == "database.host"
        assert change.old_value == "localhost"
        assert change.new_value == "db.example.com"

    def test_detect_changes_delete(self):
        """Test detecting a delete change."""
        old_config = {"database": {"host": "localhost", "port": 5432}}
        new_config = {"database": {"port": 5432}}

        change = ChangeTracker.detect_changes(old_config, new_config)[1]

        assert change is not None
        assert change.change_type == ChangeType.DELETE
        assert change.path == "database.host"
        assert change.old_value == "localhost"
        assert change.new_value is None

    def test_detect_changes_no_change(self):
        """Test when no change is detected."""
        old_config = {"database": {"host": "localhost"}}
        new_config = {"database": {"host": "localhost"}}

        change = ChangeTracker.detect_changes(old_config, new_config)

        assert change is None or len(change) == 0

        # Also test nonexistent path
        change = ChangeTracker.detect_changes(old_config, new_config)
        assert change is None or len(change) == 0

    def test_detect_changes(self):
        """Test detecting all changes between two configs."""
        old_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "credentials": {"username": "admin", "password": "secret"},
            },
            "logging": {"level": "INFO"},
        }

        new_config = {
            "database": {
                "host": "db.example.com",  # Updated
                "port": 5432,  # Unchanged
                "credentials": {
                    "username": "newuser",  # Updated
                    # password removed     # Deleted
                },
                "timeout": 30,  # Created
            },
            "logging": {"level": "DEBUG"},  # Updated
            "cache": {"ttl": 300},  # Created section
        }

        changes = ChangeTracker.detect_changes(old_config, new_config)

        # There should be a global change plus all the specific changes
        # We need at least 7 changes (1 global + 6 specific)
        assert len(changes) >= 7

        # Verify global change is first
        assert changes[0].change_type == ChangeType.CHANGE
        assert changes[0].path == "*"

        # Check for specific changes (order may vary)
        paths_and_types = [(change.path, change.change_type) for change in changes[1:]]

        # Updates
        assert ("database.host", ChangeType.UPDATE) in paths_and_types
        assert ("database.credentials.username", ChangeType.UPDATE) in paths_and_types
        assert ("logging.level", ChangeType.UPDATE) in paths_and_types

        # Deletions
        assert ("database.credentials.password", ChangeType.DELETE) in paths_and_types

        # Creations
        assert ("database.timeout", ChangeType.CREATE) in paths_and_types
        assert ("cache", ChangeType.CREATE) in paths_and_types

    def test_detect_changes_with_lists(self):
        """Test detecting changes in lists."""
        old_config = {
            "servers": [{"host": "server1", "port": 8080}, {"host": "server2", "port": 8081}]
        }

        new_config = {
            "servers": [
                {"host": "server1", "port": 8443},  # Updated port
                {"host": "server3", "port": 8081},  # Different server
            ]
        }

        changes = ChangeTracker.detect_changes(old_config, new_config)

        # Should detect the list change
        assert any(
            change.path == "servers" and change.change_type == ChangeType.UPDATE
            for change in changes
        )

    def test_detect_changes_with_empty_configs(self):
        """Test with empty configs."""
        # Both empty
        changes = ChangeTracker.detect_changes({}, {})
        assert len(changes) == 0

        # Old empty, new has values
        changes = ChangeTracker.detect_changes({}, {"key": "value"})
        assert len(changes) >= 2  # Global change + key creation

        # New empty, old has values
        changes = ChangeTracker.detect_changes({"key": "value"}, {})
        assert len(changes) >= 2  # Global change + key deletion

    def test_detect_changes_identical_configs(self):
        """Test with identical configs."""
        config = {"database": {"host": "localhost"}}
        changes = ChangeTracker.detect_changes(config, config)
        assert len(changes) == 0

    def test_walk_changes_generation(self):
        """Test the internal _walk_changes method."""
        old_data = {"a": 1, "b": {"c": 2}}
        new_data = {"a": 1, "b": {"d": 3}}

        # Convert generator to list
        changes = list(ChangeTracker._walk_changes(old_data, new_data))

        # Should detect changes in b.c (deleted) and b.d (created)
        assert any(path == "b.c" for path, _ in changes)
        assert any(path == "b.d" for path, _ in changes)
