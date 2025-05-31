"""Integration tests for NekoConf combining event pipeline and TOML support."""

import asyncio
import os
import shutil
import tempfile

import pytest

from nekoconf.core.config import NekoConf
from nekoconf.event.pipeline import EventType

# Skip tests if tomli/tomli_w packages are not available
try:
    import tomli
    import tomli_w

    has_toml = True
except ImportError:
    try:
        import tomllib as tomli

        import tomli_w

        has_toml = True
    except ImportError:
        has_toml = False


class TestIntegration:
    """Test cases for integrating event pipeline with different file formats."""

    def setup_method(self):
        """Set up test environment before each test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.yaml_path = os.path.join(self.temp_dir, "config.yaml")
        self.json_path = os.path.join(self.temp_dir, "config.json")
        self.toml_path = os.path.join(self.temp_dir, "config.toml")

        # Create initial config files
        self._create_initial_configs()

    def teardown_method(self):
        """Clean up after each test method."""
        # Use shutil.rmtree to recursively remove the directory and all its contents
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error cleaning up temporary directory: {e}")

    def _create_initial_configs(self):
        """Create initial config files in different formats."""
        # Base configuration
        config = {
            "server": {"host": "localhost", "port": 8000},
            "database": {"url": "sqlite:///data.db", "pool_size": 5},
            "logging": {"level": "INFO", "file": "app.log"},
        }

        # Create configs in different formats
        yaml_config = NekoConf(self.yaml_path)
        yaml_config.data = config.copy()
        yaml_config.save()

        json_config = NekoConf(self.json_path)
        json_config.data = config.copy()
        json_config.save()

        if has_toml:
            toml_config = NekoConf(self.toml_path)
            toml_config.data = config.copy()
            toml_config.save()

    def test_database_connection_event_handler(self):
        """Test a practical event handler for database connection changes."""
        connection_events = []
        reconnects = 0

        # Create configuration client
        client = NekoConf(self.yaml_path, event_emission_enabled=True)

        # Register handlers for database connection changes
        @client.on_change("database.url")
        def handle_db_url_change(old_value, new_value, **kwargs):
            connection_events.append(("url_changed", old_value, new_value))
            nonlocal reconnects
            reconnects += 1

        @client.on_change("database.pool_size")
        def handle_pool_size_change(old_value, new_value, **kwargs):
            connection_events.append(("pool_size_changed", old_value, new_value))

        # Make changes to trigger events
        client.set("database.url", "postgresql://user:pass@localhost/db")
        client.set("database.pool_size", 10)

        # Check results
        assert len(connection_events) == 2
        assert connection_events[0] == (
            "url_changed",
            "sqlite:///data.db",
            "postgresql://user:pass@localhost/db",
        )
        assert connection_events[1] == ("pool_size_changed", 5, 10)
        assert reconnects == 1  # Only URL change should trigger reconnect

    def test_logging_configuration_handler(self):
        """Test a practical event handler for logging configuration changes."""
        log_config_changes = []

        # Create configuration client
        client = NekoConf(self.json_path, event_emission_enabled=True)

        # Register a handler for all logging changes
        @client.on_event(EventType.CHANGE, "logging.*")
        def handle_logging_change(path, old_value, new_value, config_data, **kwargs):
            log_config_changes.append((path, old_value, new_value))

        # Make changes
        client.set("logging.level", "DEBUG")
        client.set("logging.file", "debug.log")
        client.set("logging.console", True)  # New setting

        # Check results
        assert len(log_config_changes) == 3
        assert ("logging.level", "INFO", "DEBUG") in log_config_changes
        assert ("logging.file", "app.log", "debug.log") in log_config_changes
        assert ("logging.console", None, True) in log_config_changes

    @pytest.mark.skipif(not has_toml, reason="TOML support not available")
    def test_feature_flags_with_toml(self):
        """Test feature flags implementation with TOML config."""
        enabled_features = set()
        disabled_features = set()

        # Create configuration client with TOML
        client = NekoConf(self.toml_path, event_emission_enabled=True)

        # Add some feature flags
        client.set("features.enable_cache", True)
        client.set("features.dark_mode", False)
        client.set("features.experimental.new_ui", True)

        # Register handlers for feature flag changes
        @client.on_change("features.*")
        def handle_feature_change(event_type, path, old_value, new_value, config_data, **kwargs):
            feature_name = path.split(".")[-1]
            if new_value:
                enabled_features.add(feature_name)
                if feature_name in disabled_features:
                    disabled_features.remove(feature_name)
            else:
                disabled_features.add(feature_name)
                if feature_name in enabled_features:
                    enabled_features.remove(feature_name)

        # Make some changes
        client.set("features.dark_mode", True)  # Enable
        client.set("features.enable_cache", False)  # Disable
        client.set("features.analytics", True)  # New feature

        # Check results
        assert "dark_mode" in enabled_features
        assert "analytics" in enabled_features
        assert "enable_cache" in disabled_features
        assert "new_ui" not in enabled_features  # Not directly under features.*

    def test_multi_format_integration(self):
        """Test that event handlers work across config formats."""
        if not has_toml:
            pytest.skip("TOML support not available")

        server_updates = {"yaml": 0, "json": 0, "toml": 0}

        # Create clients for each format
        yaml_client = NekoConf(self.yaml_path, event_emission_enabled=True)
        json_client = NekoConf(self.json_path, event_emission_enabled=True)
        toml_client = NekoConf(self.toml_path, event_emission_enabled=True)

        # Register similar handlers for each
        @yaml_client.on_change("server.host")
        def handle_yaml_host_change(old_value, new_value, **kwargs):
            server_updates["yaml"] += 1

        @json_client.on_change("server.host")
        def handle_json_host_change(old_value, new_value, **kwargs):
            server_updates["json"] += 1

        @toml_client.on_change("server.host")
        def handle_toml_host_change(old_value, new_value, **kwargs):
            server_updates["toml"] += 1

        # Make changes to each config
        yaml_client.set("server.host", "yaml-server")
        json_client.set("server.host", "json-server")
        toml_client.set("server.host", "toml-server")

        # Check that each handler was called once
        assert server_updates["yaml"] == 1
        assert server_updates["json"] == 1
        assert server_updates["toml"] == 1

    @pytest.mark.asyncio
    async def test_async_pipeline_with_toml(self):
        """Test asynchronous event handlers with TOML config."""
        if not has_toml:
            pytest.skip("TOML support not available")

        async_event_order = []

        # Create configuration manager
        config = NekoConf(self.toml_path, event_emission_enabled=True)

        # Register async handlers with different priorities
        @config.on_change("server.host")
        async def async_handler_low_priority(old_value, new_value, **kwargs):
            # This should execute last due to lower priority (default 100)
            await asyncio.sleep(0.01)  # Simulate async work
            async_event_order.append("low")

        @config.on_change("server.host", priority=50)
        async def async_handler_medium_priority(old_value, new_value, **kwargs):
            # This should execute second
            await asyncio.sleep(0.01)  # Simulate async work
            async_event_order.append("medium")

        @config.on_change("server.host", priority=10)
        async def async_handler_high_priority(old_value, new_value, **kwargs):
            # This should execute first due to highest priority
            await asyncio.sleep(0.01)  # Simulate async work
            async_event_order.append("high")

        # Set the value to trigger handlers
        config.set("server.host", "async-server")

        # Wait for all handlers to complete
        await asyncio.sleep(0.05)

        # Check execution order
        assert async_event_order == ["high", "medium", "low"]

    def test_bulk_operations_events(self):
        """Test that bulk operations trigger appropriate events."""
        bulk_events = []

        # Create configuration client
        client = NekoConf(self.yaml_path, event_emission_enabled=True)

        # Clear any existing handlers to avoid test interference
        client.event_pipeline.handlers = []

        # Register a fresh handler for any change
        @client.on_event(EventType.CHANGE, "@global")
        def handle_any_change(event_type, **kwargs):
            # Track the event
            bulk_events.append("bulk_change")

        # Perform a bulk update - explicitly skip the save() to avoid double events
        client.update({"server": {"host": "updated-host", "port": 9000}})

        # Check results - should have exactly 1 event from the bulk update
        assert len(bulk_events) == 1, f"Expected 1 bulk event but got {len(bulk_events)}"
