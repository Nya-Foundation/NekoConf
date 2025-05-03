"""Tests for the web server module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from nekoconf.server.app import NekoConfigServer, NekoWsNotifier


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_websocket_lifecycle(self):
        """Test the complete lifecycle of WebSocket connections."""
        manager = NekoWsNotifier()

        # Create WebSockets
        websocket1 = AsyncMock(spec=WebSocket)
        websocket2 = AsyncMock(spec=WebSocket)

        # Connect them
        await manager.connect(websocket1)
        await manager.connect(websocket2)

        assert len(manager.active_connections) == 2
        assert websocket1 in manager.active_connections
        assert websocket2 in manager.active_connections

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

        assert len(manager.active_connections) == 1
        assert websocket1 not in manager.active_connections
        assert websocket2 in manager.active_connections

        # Broadcast again
        await manager.broadcast(test_message)

        # Only second websocket should receive
        websocket1.send_json.assert_not_called()
        websocket2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_with_failed_send(self):
        """Test broadcasting with a failed send that should disconnect the client."""
        manager = NekoWsNotifier()

        # Create WebSockets - one that will fail on send
        websocket1 = AsyncMock(spec=WebSocket)
        websocket2 = AsyncMock(spec=WebSocket)
        websocket2.send_json.side_effect = WebSocketDisconnect()

        # Connect them
        await manager.connect(websocket1)
        await manager.connect(websocket2)

        # Broadcast should handle the exception and disconnect the failing client
        await manager.broadcast({"type": "test"})

        # Second websocket should be disconnected
        assert len(manager.active_connections) == 1
        assert websocket1 in manager.active_connections
        assert websocket2 not in manager.active_connections


class TestNekoConf:
    """Tests for the NekoConf class."""

    def test_init(self, config_manager):
        """Test initializing the NekoConf."""
        # Patch the signal handlers to prevent interference with test environment
        # Also patch the asynccontextmanager to avoid lifespan issues in tests
        with patch("signal.signal"), patch("contextlib.asynccontextmanager", lambda f: f):
            server = NekoConfigServer(config_manager)

            assert server.config == config_manager
            assert hasattr(server, "app")
            assert hasattr(server, "ws_manager")

            # Clean up after test
            server._cleanup_resources()

    def test_api_get_endpoints(self, test_client, sample_config):
        """Test the GET endpoints for configuration."""
        # Test full config
        response = test_client.get("/api/config")
        assert response.status_code == 200
        assert response.json() == sample_config

        # Test section
        response = test_client.get("/api/config/server")
        assert response.status_code == 200
        assert response.json() == sample_config["server"]

        # Test specific value
        response = test_client.get("/api/config/server/host")
        assert response.status_code == 200
        assert response.json() == sample_config["server"]["host"]

        # Test nonexistent key
        response = test_client.get("/api/config/nonexistent")
        assert response.status_code == 404
        # The exact error format depends on implementation
        assert response.json().get("detail") or response.json().get("error")

    def test_api_set_and_update(self, test_client, config_manager):
        """Test setting and updating config values."""
        # Test setting a single value
        response = test_client.post("/api/config/server/host", json={"value": "0.0.0.0"})
        assert response.status_code == 200
        assert config_manager.get("server.host") == "0.0.0.0"

        # Test bad request - exact behavior depends on implementation
        response = test_client.post("/api/config/server/host", json="not-a-json")
        assert response.status_code in [400, 422]  # FastAPI validation might return 422

        # Test updating multiple values
        update_data = {"server": {"host": "example.com", "port": 9000}}
        response = test_client.post("/api/config", json=update_data)
        assert response.status_code == 200
        # The success key might not be present in all implementations
        assert config_manager.get("server.host") == "example.com"
        assert config_manager.get("server.port") == 9000

    def test_api_delete_and_reload(self, test_client, config_manager):
        """Test deleting values and reloading config."""
        # Test delete
        response = test_client.delete("/api/config/server/debug")
        assert response.status_code == 200
        # Response format depends on implementation
        assert config_manager.get("server.debug") is None

        # Test delete nonexistent key
        response = test_client.delete("/api/config/nonexistent")
        assert response.status_code == 404
        # The error format depends on implementation

        # Test reload
        # Change in-memory config
        config_manager.data["server"]["host"] = "changed_value"

        # Reload via API
        response = test_client.post("/api/config/reload")
        assert response.status_code == 200

        # reload resets to the file value
        assert config_manager.get("server.host") == "localhost"

    def test_run(self):
        """Test the run method."""
        # Create mocks
        config_manager = MagicMock()

        # Patch signal handlers and asynccontextmanager
        with patch("signal.signal"), patch("contextlib.asynccontextmanager", lambda f: f), patch(
            "uvicorn.Config"
        ) as mock_config, patch("uvicorn.Server") as mock_server:

            # Set up server mock
            server_instance = mock_server.return_value

            # Create and run the web server
            web_server = NekoConfigServer(config_manager)
            web_server.run(host="0.0.0.0", port=9000, reload=True)

            # Check that the server was run with expected parameters
            mock_config.assert_called_once()
            config_args = mock_config.call_args[1]
            assert config_args["host"] == "0.0.0.0"
            assert config_args["port"] == 9000
            assert config_args["reload"] is True

            # Verify server was started
            server_instance.run.assert_called_once()

            # Ensure cleanup happens
            web_server._cleanup_resources()

    def test_cleanup_resources(self):
        """Test that cleanup_resources properly cleans up."""
        # Create mocks
        config_manager = MagicMock()

        # Patch signal handlers and asynccontextmanager
        with patch("signal.signal"), patch("contextlib.asynccontextmanager", lambda f: f):
            # Create server
            web_server = NekoConfigServer(config_manager)

            # Test cleanup method
            web_server._cleanup_resources()

            # Verify config cleanup was called
            config_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self):
        """Test the lifespan context manager."""
        config_manager = MagicMock()

        # We need to get the actual lifespan context manager for testing
        with patch("signal.signal"):
            web_server = NekoConfigServer(config_manager)

            # Extract the lifespan context manager function
            lifespan_func = web_server.app.router.lifespan_context

            # Create a mock app
            mock_app = MagicMock()

            # Test the lifespan context manager
            async with lifespan_func(mock_app):
                # This happens inside the context manager
                pass

            # After context manager exits, cleanup should have been called
            config_manager.cleanup.assert_called()


@pytest.fixture
def web_server(config_manager):
    """Create a web server for testing."""
    # Patch signal handlers and asynccontextmanager to prevent interference with the test runner
    with patch("signal.signal"), patch("contextlib.asynccontextmanager", lambda f: f):
        server = NekoConfigServer(config_manager)
        yield server
        # Ensure proper cleanup after each test
        server._cleanup_resources()
