"""Web server module for NekoConf.

This module provides a web interface for managing configuration files.
"""

import asyncio
import importlib.resources
import json
import logging
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from nekoconf._version import __version__
from nekoconf.core.config import NekoConfigManager  # Updated import path
from nekoconf.utils.helper import getLogger

from .auth import AuthMiddleware, NekoAuthGuard  # Relative import within web package


class NekoWsNotifier:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        """Initialize the WebSocket manager."""
        self.logger = logger or getLogger(__name__)
        self.active_connections: List[WebSocket] = []  # Changed from Set to List

    async def connect(self, websocket: WebSocket) -> None:
        """Connect a new WebSocket client.

        Args:
            websocket: The WebSocket connection to add
        """
        await websocket.accept()
        self.active_connections.append(websocket)  # Changed from add to append
        self.logger.debug(
            f"WebSocket client connected, total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket client.

        Args:
            websocket: The WebSocket connection to remove
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.debug(
                f"WebSocket client disconnected, remaining connections: {len(self.active_connections)}"
            )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSocket clients.

        Args:
            message: The message to broadcast
        """
        if not self.active_connections:
            return

        # Use a copy of the list to avoid modification during iteration
        disconnected = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up any failed connections
        for connection in disconnected:
            self.disconnect(connection)


class NekoConfigServer:
    """NekoConf API and Web server for configuration management."""

    def __init__(
        self,
        config: NekoConfigManager,
        api_key: Optional[str] = None,
        read_only: bool = False,
        logger: Optional[logging.Logger] = None,
        register_signals: bool = True,  # Add this parameter
    ) -> None:
        """Initialize the api and web server.

        Args:
            config: NekoConfig instance for managing configuration
            api_key: Optional API key for authentication
            read_only: If True, disables write operations
            logger: Optional custom logger, defaults to module logger
            register_signals: If True, registers signal handlers for graceful shutdown
        """
        self.config = config
        self.read_only = read_only
        self.logger = logger or config.logger or getLogger(__name__)
        self._shutdown_requested = False
        self._server = None

        # Try to get the static directory using importlib.resources (Python 3.7+)
        # Path adjusted for the new location within the 'web' subpackage
        self.www_dir = Path(importlib.resources.files("nekoconf.server") / "html")
        self.static_dir = self.www_dir / "static"

        print(f"Static directory: {self.static_dir.resolve()}")
        self.templates = Jinja2Templates(directory=str(self.www_dir))

        self.logger.info(f"Static resources directory set to: {self.www_dir.resolve()}")

        # Define the lifespan context manager for the app
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup code (previously in on_startup)
            self.logger.info("Starting up NekoConf server...")
            yield
            # Shutdown code (previously in on_shutdown)
            self.logger.info("Shutting down NekoConf server...")
            await self._cleanup_on_shutdown()

        self.app = FastAPI(
            title="NekoConf",
            description="A cute configuration management tool",
            version=__version__,
            lifespan=lifespan,  # Use the lifespan context manager
        )

        self.ws_manager = NekoWsNotifier(logger=self.logger)

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add authentication middleware if an API key is provided
        if api_key:
            self.auth = NekoAuthGuard(api_key=api_key)  # Pass api_key to AuthManager
            self.app.add_middleware(AuthMiddleware, auth=self.auth, logger=self.logger)

        # Set up routes
        self._setup_routes()
        self._setup_config_change_listener()

        # Only set up signal handlers if requested
        if register_signals:
            self._setup_signal_handlers()

    def _setup_config_change_listener(self):
        """Set up a listener for configuration changes."""

        from nekoconf.event.pipeline import EventType

        # Register the handler for global configuration changes only
        self.config.event_pipeline.register_handler(
            self._on_config_change, EventType.CHANGE, path_pattern="@global"
        )

    async def _on_config_change(
        self,
        event_type=None,
        path=None,
        old_value=None,
        new_value=None,
        config_data=None,
        **kwargs,
    ) -> None:
        self.logger.info("Configuration changed, broadcasting update to WebSocket clients")

        # Broadcast the updated configuration to all connected WebSocket clients
        await self.ws_manager.broadcast({"type": "update", "data": self.config.data})

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        # Store original signal handlers so we can chain them
        original_sigint = signal.getsignal(signal.SIGINT)
        original_sigterm = signal.getsignal(signal.SIGTERM)

        def signal_handler(sig, frame):
            self.logger.info(f"Received signal {sig}, initiating cleanup...")
            self._shutdown_requested = True
            self._cleanup_resources()

            # Call original handler after cleanup
            # This ensures the parent app's signal handling still works
            if callable(original_sigint if sig == signal.SIGINT else original_sigterm):
                original_handler = original_sigint if sig == signal.SIGINT else original_sigterm
                original_handler(sig, frame)

        # Register signal handlers for SIGINT and SIGTERM
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _cleanup_on_shutdown(self):
        """Cleanup resources when FastAPI shuts down."""
        self.logger.info("FastAPI shutdown event triggered, cleaning up resources...")
        self._cleanup_resources()

    def _cleanup_resources(self):
        """Clean up all resources used by the server."""
        try:
            # Clean up configuration manager resources (including lock files)
            if hasattr(self, "config") and self.config:
                self.logger.info("Cleaning up configuration resources...")
                self.config.cleanup()

            self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _setup_routes(self) -> None:
        """Set up API routes and static file serving."""

        # API endpoints
        @self.app.get("/api/config", response_class=JSONResponse)
        def get_config():
            """Get the entire configuration."""
            return self.config.get()

        @self.app.get("/api/config/{key_path:path}", response_class=JSONResponse)
        def get_config_path(key_path: str):
            """Get a specific configuration path."""

            # convert key_path to JMESPath expressions
            key_path = key_path.replace("/", ".")

            value = self.config.get(key_path)
            if value is None:
                raise HTTPException(status_code=404, detail=f"Path {key_path} not found")
            return value

        @self.app.post("/api/config", response_class=JSONResponse)
        async def update_config(data: Dict[str, Any]):
            """Update multiple configuration values."""
            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            errors = self.config.validate_schema(data)
            if errors:
                self.logger.warning(f"Configuration validation errors: {errors}")
                return {"valid": False, "errors": errors}

            is_updated = self.config.replace(data)

            if is_updated:
                self.config.save()

            return {"status": "success"}

        @self.app.post("/api/config/reload", response_class=JSONResponse)
        async def reload_config():
            """Reload configuration from disk."""
            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            self.config.load()
            return {"status": "success"}

        @self.app.post("/api/config/validate", response_class=JSONResponse)
        async def validate_config():
            """Validate the current configuration against the schema."""
            errors = self.config.validate()

            if errors:
                self.logger.warning(f"Configuration validation errors: {errors}")
                return {"valid": False, "errors": errors}
            return {"valid": True}

        @self.app.post("/api/config/{key_path:path}", response_class=JSONResponse)
        async def set_config(key_path: str, data: Dict[str, Any]):
            """Set a specific configuration path."""

            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            # convert key_path to JMESPath expressions
            key_path = key_path.replace("/", ".")

            self.config.set(key_path, data.get("value"))
            errors = self.config.validate()
            if errors:
                self.logger.warning(f"Configuration validation errors: {errors}")
                return {"valid": False, "errors": errors}

            self.config.save()
            return {"status": "success"}

        @self.app.delete("/api/config/{key_path:path}", response_class=JSONResponse)
        async def delete_config(key_path: str):
            """Delete a specific configuration path."""

            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            # convert key_path to JMESPath expressions
            key_path = key_path.replace("/", ".")

            if self.config.delete(key_path):
                errors = self.config.validate()
                if errors:
                    self.logger.warning(f"Configuration validation errors: {errors}")
                    return {"valid": False, "errors": errors}

                self.config.save()
                return {"status": "success"}
            else:
                raise HTTPException(status_code=404, detail=f"Path {key_path} not found")

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.ws_manager.connect(websocket)
            try:
                # Send initial configuratio`n
                await websocket.send_json({"type": "config", "data": self.config.get()})

                # Keep the connection open, handle incoming messages
                while True:
                    try:
                        data = await websocket.receive_json()
                        # We could implement commands here later
                        self.logger.debug(f"Received WebSocket message: {data}")
                    except json.JSONDecodeError:
                        self.logger.warning("Received invalid JSON through WebSocket")
            except WebSocketDisconnect:
                self.ws_manager.disconnect(websocket)

        # Serve static files if the directory exists
        if self.www_dir.exists() and self.www_dir.is_dir() and self.static_dir.exists():
            """Serve static files from the static directory."""

            @self.app.get("/", response_class=HTMLResponse)
            def get_index(request: Request):
                """Serve the main UI page."""
                return self.templates.TemplateResponse("index.html", {"request": request})

            @self.app.get("/favicon.ico")
            async def get_favicon():
                """Serve the favicon."""
                return FileResponse(self.www_dir / "favicon.ico")

            @self.app.get("/static/logo.svg")
            async def get_logo():
                """Serve the logo."""

                return FileResponse(self.static_dir / "logo.svg")

            @self.app.get("/login.html", response_class=HTMLResponse)
            def get_login(request: Request):
                """Serve the login page."""
                return self.templates.TemplateResponse(
                    "login.html", {"request": request, "return_path": "/"}
                )

            @self.app.get("/static/script.js")
            async def get_script():
                return FileResponse(
                    self.static_dir / "script.js",
                    media_type="application/javascript",
                )

            @self.app.get("/static/styles.css")
            async def get_style():
                return FileResponse(self.static_dir / "styles.css", media_type="text/css")

        # Add health check and shutdown endpoints
        @self.app.get("/health")
        def health_check():
            """Health check endpoint."""
            return {"status": "ok", "version": __version__}

        @self.app.post("/shutdown")
        async def trigger_shutdown():
            """Trigger a graceful shutdown of the server."""
            if not self.read_only:  # Only allow in non-read-only mode for security
                self.logger.info("Shutdown requested via API")
                # Schedule shutdown to happen after response is sent
                asyncio.create_task(self._delayed_shutdown())
                return {"status": "shutdown_initiated"}
            raise HTTPException(status_code=403, detail="Shutdown not allowed in read-only mode")

    async def _delayed_shutdown(self):
        """Perform delayed shutdown to allow response to be sent first."""
        await asyncio.sleep(0.5)  # Short delay to ensure response is sent
        self._cleanup_resources()
        if self._server:
            self.logger.info("Stopping server...")
            self._server.should_exit = True

    async def start_background(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
    ):
        """Start the dashboard server in the background."""

        self.logger.info(f"Starting NekoConf Server at http://{host}:{port} in the background")

        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info", reload=reload)
        server = uvicorn.Server(config)
        self._server = server
        await server.serve()

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
    ) -> None:
        """Run the web server.

        Args:
            host: Host to bind to
            port: Port to listen on
            reload: Whether to enable auto-reload for development
        """
        self.logger.info(f"Starting NekoConf Server at http://{host}:{port}")

        try:
            # Create a custom uvicorn config and server
            config = uvicorn.Config(app=self.app, host=host, port=port, reload=reload)
            server = uvicorn.Server(config)
            self._server = server

            # Run the server
            server.run()
        except KeyboardInterrupt:
            self.logger.info("Server interrupted, cleaning up...")
            self._cleanup_resources()
        except Exception as e:
            self.logger.error(f"Server error: {e}")
            self._cleanup_resources()
        finally:
            self.logger.info("Server stopped")
