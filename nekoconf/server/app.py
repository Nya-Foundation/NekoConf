"""Web server module for NekoConf.

This module provides a web interface for managing configuration files.
"""

import importlib.resources
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from nekoconf._version import __version__
from nekoconf.core.config import NekoConfigManager  # Updated import path
from nekoconf.core.utils import getLogger

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
    ) -> None:
        """Initialize the api and web server.

        Args:
            config: NekoConfig instance for managing configuration
            api_key: Optional API key for authentication
            read_only: If True, disables write operations
            logger: Optional custom logger, defaults to module logger
        """
        self.config = config
        self.read_only = read_only
        self.logger = logger or config.logger or getLogger(__name__)

        # Try to get the static directory using importlib.resources (Python 3.7+)
        # Path adjusted for the new location within the 'web' subpackage
        self.static_dir = Path(importlib.resources.files("nekoconf.server") / "static")
        self.templates = Jinja2Templates(directory=str(self.static_dir))

        self.logger.info(f"Static resources directory set to: {self.static_dir.resolve()}")

        self.app = FastAPI(
            title="NekoConf",
            description="A cute configuration management tool",
            version=__version__,
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

        # Register as configuration observer
        self.config.register_observer(self._on_config_change)

        # Set up routes
        self._setup_routes()

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

            # convert key_path to dot notation
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

            self.config.update(data)

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
                return {"valid": False, "errors": errors}
            return {"valid": True}

        @self.app.post("/api/config/{key_path:path}", response_class=JSONResponse)
        async def set_config(key_path: str, data: Dict[str, Any]):
            """Set a specific configuration path."""

            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            # convert key_path to dot notation
            key_path = key_path.replace("/", ".")

            self.config.set(key_path, data.get("value"))
            self.config.save()
            return {"status": "success"}

        @self.app.delete("/api/config/{key_path:path}", response_class=JSONResponse)
        async def delete_config(key_path: str):
            """Delete a specific configuration path."""

            if self.read_only:
                raise HTTPException(status_code=403, detail="Read-only mode is enabled")

            # convert key_path to dot notation
            key_path = key_path.replace("/", ".")

            if self.config.delete(key_path):
                self.config.save()
                return {"status": "success"}
            else:
                raise HTTPException(status_code=404, detail=f"Path {key_path} not found")

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.ws_manager.connect(websocket)
            try:
                # Send initial configuration
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
        if self.static_dir.exists() and self.static_dir.is_dir():
            """Serve static files from the static directory."""

            @self.app.get("/", response_class=HTMLResponse)
            def get_index(request: Request):
                """Serve the main UI page."""
                return self.templates.TemplateResponse("index.html", {"request": request})

            @self.app.get("/login.html", response_class=HTMLResponse)
            def get_login(request: Request):
                """Serve the login page."""
                return self.templates.TemplateResponse("login.html", {"return_path": "/"})

            @self.app.get("/static/script.js")
            def get_script(request: Request):
                return self.templates.TemplateResponse(
                    "script.js", {"request": request}, media_type="application/javascript"
                )

            @self.app.get("/static/styles.css")
            def get_style(request: Request):
                return self.templates.TemplateResponse(
                    "styles.css", {"request": request}, media_type="text/css"
                )

    async def _on_config_change(self, config_data: Dict[str, Any]) -> None:
        """Handle configuration changes.

        Args:
            config_data: Updated configuration data
        """
        await self.ws_manager.broadcast({"type": "config", "data": config_data})

    async def start_background(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ):
        """Start the dashboard server in the background."""

        self.logger.info(f"Starting NekoConf Server at http://{host}:{port} in the background")

        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info", reload=reload)
        server = uvicorn.Server(config)
        await server.serve()

    def run(
        self,
        host: str = "127.0.0.1",
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

        uvicorn.run(app=self.app, host=host, port=port, reload=reload, log_config=None)
