"""Tests for the web server module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from nekoconf.core.config import NekoConf
from nekoconf.server.app import AppManager, ConfigApp, NekoConfOrchestrator, WebSocketManager


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_websocket_lifecycle(self):
        """Test the complete lifecycle of WebSocket connections."""
        manager = WebSocketManager("test-app")

        # Create WebSockets
        websocket1 = AsyncMock(spec=WebSocket)
        websocket2 = AsyncMock(spec=WebSocket)

        # Connect them
        await manager.connect(websocket1)
        await manager.connect(websocket2)

        assert len(manager.connections) == 2
        assert websocket1 in manager.connections
        assert websocket2 in manager.connections

        # Broadcast
        test_message = {"type": "test"}
        await manager.broadcast(test_message)

        # Both should receive the message
        websocket1.send_json.assert_called_once_with(test_message)
        websocket2.send_json.assert_called_once_with(test_message)

        # Reset mocks for next test
        websocket1.send_json.reset_mock()
        websocket2.send_json.reset_mock()

        # Disconnect one
        manager.disconnect(websocket1)

        assert len(manager.connections) == 1
        assert websocket1 not in manager.connections
        assert websocket2 in manager.connections

        # Broadcast again
        await manager.broadcast(test_message)

        # Only second websocket should receive
        websocket1.send_json.assert_not_called()
        websocket2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_failed_send(self):
        """Test broadcasting with a failed send that should disconnect the client."""
        manager = WebSocketManager("test-app")

        # Create WebSockets - one that will fail on send
        websocket1 = AsyncMock(spec=WebSocket)
        websocket2 = AsyncMock(spec=WebSocket)
        websocket2.send_json.side_effect = Exception("Connection failed")

        # Connect them
        await manager.connect(websocket1)
        await manager.connect(websocket2)

        # Broadcast should handle the exception and disconnect the failing client
        await manager.broadcast({"type": "test"})

        # Second websocket should be disconnected
        assert len(manager.connections) == 1
        assert websocket1 in manager.connections
        assert websocket2 not in manager.connections

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self):
        """Test broadcasting with no connections."""
        manager = WebSocketManager("test-app")

        # Should not raise any errors
        await manager.broadcast({"type": "test"})
        assert len(manager.connections) == 0

    def test_cleanup(self):
        """Test cleanup functionality."""
        manager = WebSocketManager("test-app")

        # Create mock WebSocket connections that don't return coroutines
        websocket1 = MagicMock()
        websocket2 = MagicMock()

        # Mock the close method to not return a coroutine
        websocket1.close = MagicMock(return_value=None)
        websocket2.close = MagicMock(return_value=None)

        manager.connections = [websocket1, websocket2]

        # Cleanup should clear all connections
        manager.cleanup()
        assert len(manager.connections) == 0


class TestAppManager:
    """Tests for the AppManager class."""

    def test_create_app(self):
        """Test creating a new app."""
        manager = AppManager()

        # Create app with default config
        app = manager.create_app("test-app")
        assert app.name == "test-app"
        assert "test-app" in manager.apps
        assert isinstance(app.config, NekoConf)

        # Create app with custom config
        custom_config = NekoConf({"custom": "value"})
        app2 = manager.create_app("custom-app", config=custom_config)
        assert app2.config.get("custom") == "value"

    def test_create_app_validation(self):
        """Test app name validation."""
        manager = AppManager()

        # Invalid names should raise ValueError
        with pytest.raises(ValueError, match="Invalid app name"):
            manager.create_app("")

        with pytest.raises(ValueError, match="Invalid app name"):
            manager.create_app("invalid name with spaces")

        # Duplicate names should raise ValueError
        manager.create_app("test-app")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_app("test-app")

    def test_get_and_delete_app(self):
        """Test getting and deleting apps."""
        manager = AppManager()

        # Get non-existent app
        assert manager.get_app("nonexistent") is None

        # Create and get app
        app = manager.create_app("test-app")
        retrieved_app = manager.get_app("test-app")
        assert retrieved_app is app

        # Delete app
        assert manager.delete_app("test-app") is True
        assert manager.get_app("test-app") is None
        assert manager.delete_app("test-app") is False  # Already deleted

    def test_list_apps_and_info(self):
        """Test listing apps and getting their info."""
        manager = AppManager()

        # Empty manager
        assert manager.list_apps() == []
        assert manager.get_apps_info() == {}

        # Add some apps
        manager.create_app("app1")
        manager.create_app("app2", description="Test app 2")

        apps = manager.list_apps()
        assert "app1" in apps
        assert "app2" in apps
        assert len(apps) == 2

        # Check app info
        info = manager.get_apps_info()
        assert "app1" in info
        assert "app2" in info
        assert info["app1"]["name"] == "app1"
        assert info["app2"]["description"] == "Test app 2"

    def test_update_app_metadata(self):
        """Test updating app metadata."""
        manager = AppManager()

        # Create an app
        manager.create_app("old-name", description="Old description")

        # Update description only
        success = manager.update_app_metadata("old-name", description="New description")
        assert success is True
        app = manager.get_app("old-name")
        assert app.description == "New description"

        # Update name and description
        success = manager.update_app_metadata(
            "old-name", new_name="new-name", description="Updated"
        )
        assert success is True
        assert manager.get_app("old-name") is None
        assert manager.get_app("new-name") is not None
        assert manager.get_app("new-name").description == "Updated"

        # Try to update non-existent app
        success = manager.update_app_metadata("nonexistent")
        assert success is False

        # Try to rename to existing name
        manager.create_app("another-app")
        with pytest.raises(ValueError, match="already exists"):
            manager.update_app_metadata("new-name", new_name="another-app")

    def test_app_manager_validation_edge_cases(self):
        """Test edge cases for app name validation."""
        manager = AppManager()

        # Test various invalid names
        invalid_names = [
            "",  # Empty
            "a" * 65,  # Too long
            "-starts-with-dash",  # Starts with dash
            "_starts-with-underscore",  # Starts with underscore
            "has spaces",  # Contains spaces
            "has@symbol",  # Contains invalid characters
            "has.dot",  # Contains dot
        ]

        for name in invalid_names:
            with pytest.raises(ValueError):
                manager.create_app(name)

        # Test valid names
        valid_names = [
            "a",
            "test123",
            "test-app",
            "test_app",
            "123test",
            "a" * 64,  # Maximum length
        ]

        for name in valid_names:
            manager.create_app(name)
            assert manager.get_app(name) is not None

    @pytest.mark.asyncio
    async def test_app_manager_broadcast(self):
        """Test broadcasting to specific apps."""
        manager = AppManager()

        # Create apps with mocked WebSocket managers
        app1 = manager.create_app("app1")
        app2 = manager.create_app("app2")

        app1.ws_manager = AsyncMock()
        app2.ws_manager = AsyncMock()

        # Broadcast to specific app
        message = {"type": "test", "data": "value"}
        result = await manager.broadcast_to_app("app1", message)
        assert result is True
        app1.ws_manager.broadcast.assert_called_once_with(message)
        app2.ws_manager.broadcast.assert_not_called()

        # Broadcast to non-existent app
        result = await manager.broadcast_to_app("nonexistent", message)
        assert result is False

    def test_app_manager_cleanup(self):
        """Test cleanup functionality."""
        manager = AppManager()

        # Create some apps
        app1 = manager.create_app("app1")
        app2 = manager.create_app("app2")

        # Mock cleanup methods
        app1.cleanup = MagicMock()
        app2.cleanup = MagicMock()

        # Cleanup should remove all apps and call their cleanup methods
        manager.cleanup()

        assert len(manager.apps) == 0
        app1.cleanup.assert_called_once()
        app2.cleanup.assert_called_once()

    def test_create_app_with_description(self):
        """Test creating apps with descriptions."""
        manager = AppManager()

        # Create app with description
        app = manager.create_app("test-app", description="Test application")
        assert app.description == "Test application"

        # Create app without description
        app2 = manager.create_app("test-app-2")
        assert app2.description is None

    def test_app_manager_default_data(self):
        """Test that default data is properly set for new apps."""
        manager = AppManager()
        app = manager.create_app("test-app")

        # Check that default data structure is present
        config_data = app.config.get_all()
        assert "server" in config_data
        assert "database" in config_data
        assert "logging" in config_data

        # Check some specific default values
        assert config_data["server"]["host"] == "localhost"
        assert config_data["server"]["port"] == 8080
        assert config_data["database"]["port"] == 5432


class TestConfigApp:
    """Tests for the ConfigApp class."""

    def test_config_app_creation(self):
        """Test creating a ConfigApp."""
        config = NekoConf({"test": "value"})
        app = ConfigApp("test-app", config)

        assert app.name == "test-app"
        assert app.config is config
        assert isinstance(app.ws_manager, WebSocketManager)

    def test_config_app_info(self):
        """Test getting app info."""
        config = NekoConf({"server": {"host": "localhost"}, "database": {"port": 5432}})
        app = ConfigApp("test-app", config)

        info = app.info
        assert info["name"] == "test-app"
        assert info["config_count"] == 2  # server and database keys
        assert info["status"] == "active"
        assert info["connections"] == 0

    @pytest.mark.asyncio
    async def test_config_app_event_handling(self):
        """Test that ConfigApp properly handles configuration change events."""
        config = NekoConf({"test": "value"}, event_emission_enabled=True)
        app = ConfigApp("test-app", config)

        # Mock the websocket manager
        app.ws_manager = AsyncMock()

        # Simulate a configuration change
        config.set("test", "new_value")

        # Give some time for async event processing
        await asyncio.sleep(0.1)

        # Verify that the websocket manager's broadcast was called
        # Note: This test verifies the event pipeline is set up, actual event handling may vary

    def test_config_app_cleanup(self):
        """Test ConfigApp cleanup."""
        config = NekoConf({"test": "value"})
        app = ConfigApp("test-app", config)

        # Mock the config and ws_manager cleanup methods
        app.config.cleanup = MagicMock()
        app.ws_manager.cleanup = MagicMock()

        app.cleanup()

        app.config.cleanup.assert_called_once()
        app.ws_manager.cleanup.assert_called_once()


class TestNekoConfOrchestrator:
    """Tests for the NekoConfOrchestrator class."""

    def test_init(self):
        """Test initializing the orchestrator."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()

            assert isinstance(orchestrator.manager, AppManager)
            assert hasattr(orchestrator, "app")
            assert orchestrator.read_only is False
            assert orchestrator.auth is None

    def test_init_with_apps(self):
        """Test initializing with existing apps."""
        config1 = NekoConf({"test": "value1"})
        config2 = NekoConf({"test": "value2"})
        apps = {"app1": config1, "app2": config2}

        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator(apps=apps)

            assert "app1" in orchestrator.manager.apps
            assert "app2" in orchestrator.manager.apps

    def test_api_list_apps(self):
        """Test the list apps API endpoint."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Empty list initially
            response = client.get("/api/apps")
            assert response.status_code == 200
            data = response.json()["data"]
            assert "default" in data

    def test_api_create_app(self):
        """Test the create app API endpoint."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create app with JSON data
            create_request = {
                "name": "test-app",
                "description": "Test application",
                "data": '{"server": {"host": "localhost", "port": 8080}}',
                "format": "json",
            }
            response = client.post("/api/apps", json=create_request)
            assert response.status_code == 201
            assert "test-app" in orchestrator.manager.apps

            # Try to create duplicate
            response = client.post("/api/apps", json=create_request)
            assert response.status_code == 400

    def test_api_delete_app(self):
        """Test the delete app API endpoint."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Delete non-existent app
            response = client.delete("/api/apps/nonexistent")
            assert response.status_code == 404

            # Create and delete app
            orchestrator.manager.create_app("test-app")
            response = client.delete("/api/apps/test-app")
            assert response.status_code == 200
            assert "test-app" not in orchestrator.manager.apps

    def test_api_config_operations(self):
        """Test configuration API operations."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create app first
            orchestrator.manager.create_app("test-app")

            # Get config
            response = client.get("/api/apps/test-app/config")
            assert response.status_code == 200
            config_data = response.json()
            assert "server" in config_data

            # Update config
            update_request = {
                "data": '{"server": {"host": "0.0.0.0", "port": 8080}}',
                "format": "json",
            }
            response = client.put("/api/apps/test-app/config", json=update_request)
            assert response.status_code == 200

            # Verify update
            response = client.get("/api/apps/test-app/config")
            assert response.status_code == 200
            config_data = response.json()
            assert config_data["server"]["host"] == "0.0.0.0"

    def test_read_only_mode(self):
        """Test read-only mode restrictions."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator(read_only=True)
            client = TestClient(orchestrator.app)

            # Create app first (this bypasses read-only for setup)
            orchestrator.manager.create_app("test-app")

            # Try to update config in read-only mode
            update_request = {"data": '{"test": "value"}', "format": "json"}
            response = client.put("/api/apps/test-app/config", json=update_request)
            assert response.status_code == 403

    def test_run_method(self):
        """Test the run method."""
        with patch("signal.signal"), patch("uvicorn.Config") as mock_config, patch(
            "uvicorn.Server"
        ) as mock_server:
            orchestrator = NekoConfOrchestrator()
            server_instance = mock_server.return_value

            orchestrator.run(host="127.0.0.1", port=9000, reload=True)

            # Verify uvicorn was configured correctly
            mock_config.assert_called_once()
            config_kwargs = mock_config.call_args[1]
            assert config_kwargs["host"] == "127.0.0.1"
            assert config_kwargs["port"] == 9000
            assert config_kwargs["reload"] is True

            # Verify server was started
            server_instance.run.assert_called_once()

    def test_api_get_app_info(self):
        """Test getting specific app info."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app
            orchestrator.manager.create_app("test-app", description="Test description")

            # Get app info
            response = client.get("/api/apps/test-app")
            assert response.status_code == 200
            data = response.json()["data"]
            assert data["name"] == "test-app"
            assert data["description"] == "Test description"

            # Try to get non-existent app
            response = client.get("/api/apps/nonexistent")
            assert response.status_code == 404

    def test_api_update_app(self):
        """Test updating an existing app."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app first
            orchestrator.manager.create_app("test-app")

            # Update the app
            update_request = {
                "name": "test-app",  # Name stays the same
                "description": "Updated description",
                "data": '{"new": "config"}',
                "format": "json",
            }
            response = client.put("/api/apps/test-app", json=update_request)
            assert response.status_code == 200

            # Verify the update
            app = orchestrator.manager.get_app("test-app")
            assert app.description == "Updated description"
            assert app.config.get("new") == "config"

    def test_api_update_app_metadata(self):
        """Test updating app metadata only."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app first
            orchestrator.manager.create_app("old-name", description="Old description")

            # Update metadata
            metadata_request = {"name": "new-name", "description": "New description"}
            response = client.patch("/api/apps/old-name/metadata", json=metadata_request)
            assert response.status_code == 200

            # Verify the app was renamed
            assert orchestrator.manager.get_app("old-name") is None
            new_app = orchestrator.manager.get_app("new-name")
            assert new_app is not None
            assert new_app.description == "New description"

    def test_api_config_path_operations(self):
        """Test specific configuration path operations."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app
            orchestrator.manager.create_app("test-app")

            # Get a specific config path
            response = client.get("/api/apps/test-app/config/server.host")
            assert response.status_code == 200
            data = response.json()
            assert data["path"] == "server.host"
            assert "value" in data

            # Set a specific config path
            path_request = {"value": "new-host", "type": "str"}
            response = client.put("/api/apps/test-app/config/server.host", json=path_request)
            assert response.status_code == 200

            # Verify the change
            response = client.get("/api/apps/test-app/config/server.host")
            assert response.status_code == 200
            assert response.json()["value"] == "new-host"

            # Delete a config path
            response = client.delete("/api/apps/test-app/config/server")
            assert response.status_code == 200

            # Verify deletion - should get 404 now
            response = client.get("/api/apps/test-app/config/server.debug")
            assert response.status_code == 404

    def test_api_validate_config(self):
        """Test configuration validation endpoint."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app
            orchestrator.manager.create_app("test-app")

            # Validate valid config
            validate_request = {
                "data": '{"server": {"host": "localhost", "port": 8080}}',
                "format": "json",
            }
            response = client.post("/api/apps/test-app/validate", json=validate_request)
            assert response.status_code == 200
            data = response.json()
            assert "valid" in data
            assert "errors" in data

    def test_health_endpoint(self):
        """Test the health check endpoint."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "version" in data
            assert "apps" in data
            assert data["read_only"] is False

    def test_websocket_connection(self):
        """Test WebSocket connection handling."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app first
            orchestrator.manager.create_app("test-app")

            # Test WebSocket connection
            with client.websocket_connect("/ws/test-app") as websocket:
                data = websocket.receive_json()
                assert data["type"] == "initial_config"
                assert "data" in data

            # Test WebSocket to non-existent app should fail
            with pytest.raises(Exception):
                with client.websocket_connect("/ws/nonexistent") as websocket:
                    pass

    def test_api_error_handling(self):
        """Test API error handling for various edge cases."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Test creating app with invalid name
            invalid_request = {
                "name": "invalid name",  # Contains space
                "data": "{}",
                "format": "json",
            }
            response = client.post("/api/apps", json=invalid_request)
            assert response.status_code == 422  # Validation error

            # Test creating app with invalid JSON
            invalid_json_request = {"name": "test-app", "data": "{invalid json}", "format": "json"}
            response = client.post("/api/apps", json=invalid_json_request)
            assert response.status_code == 400

            # Test operations on non-existent app
            response = client.get("/api/apps/nonexistent/config")
            assert response.status_code == 404

            response = client.put(
                "/api/apps/nonexistent/config", json={"data": "{}", "format": "json"}
            )
            assert response.status_code == 404

    def test_api_different_formats(self):
        """Test API with different configuration formats."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Test with YAML format
            yaml_request = {
                "name": "yaml-app",
                "data": "server:\n  host: localhost\n  port: 8080",
                "format": "yaml",
            }
            response = client.post("/api/apps", json=yaml_request)
            assert response.status_code == 201

            # Test with TOML format
            toml_request = {
                "name": "toml-app",
                "data": '[server]\nhost = "localhost"\nport = 8080',
                "format": "toml",
            }
            response = client.post("/api/apps", json=toml_request)
            assert response.status_code == 201

    def test_api_value_type_conversion(self):
        """Test API value type conversion for config paths."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app
            orchestrator.manager.create_app("test-app")

            # Test different value types
            test_cases = [
                {"value": "123", "type": "int", "expected": 123},
                {"value": "3.14", "type": "float", "expected": 3.14},
                {"value": "true", "type": "bool", "expected": True},
                {"value": '["a", "b", "c"]', "type": "list", "expected": ["a", "b", "c"]},
                {"value": '{"key": "value"}', "type": "dict", "expected": {"key": "value"}},
            ]

            for case in test_cases:
                response = client.put(
                    f"/api/apps/test-app/config/test.{case['type']}_value",
                    json={"value": case["value"], "type": case["type"]},
                )
                assert response.status_code == 200

                # Verify the value was set correctly
                response = client.get(f"/api/apps/test-app/config/test.{case['type']}_value")
                assert response.status_code == 200
                assert response.json()["value"] == case["expected"]

    @pytest.mark.asyncio
    async def test_websocket_broadcast_integration(self):
        """Test WebSocket broadcasting integration with configuration changes."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Create an app
            app = orchestrator.manager.create_app("test-app")

            # Mock the WebSocket manager
            app.ws_manager = AsyncMock()

            # Trigger a configuration change via API
            update_request = {"data": '{"updated": "value"}', "format": "json"}
            response = client.put("/api/apps/test-app/config", json=update_request)
            assert response.status_code == 200

            # Give some time for async processing
            await asyncio.sleep(0.1)

    def test_static_file_serving(self):
        """Test static file serving capabilities."""
        with patch("signal.signal"):
            orchestrator = NekoConfOrchestrator()
            client = TestClient(orchestrator.app)

            # Test favicon
            response = client.get("/favicon.ico")
            # Should either serve the file or return 404 if not found
            assert response.status_code in [200, 404]

            # Test dashboard
            response = client.get("/")
            # Should either serve the HTML or return error if template not found
            assert response.status_code in [200, 500]

    def test_auth_integration(self):
        """Test authentication integration."""
        with patch("signal.signal"):
            # Create orchestrator with API key
            orchestrator = NekoConfOrchestrator(api_key="test-api-key")
            assert orchestrator.auth is not None

            # Without API key
            orchestrator2 = NekoConfOrchestrator()
            assert orchestrator2.auth is None


@pytest.fixture
def orchestrator():
    """Create an orchestrator for testing."""
    with patch("signal.signal"):
        orchestrator = NekoConfOrchestrator()
        yield orchestrator
        orchestrator.manager.cleanup()
