"""Web server module for NekoConf.

This module provides a web interface for managing configuration files.
"""

import importlib.resources
import json
import logging
import secrets
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from nekoconf.config_manager import ConfigManager

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self) -> None:
        """Initialize the WebSocket manager."""
        self.active_connections: List[WebSocket] = []  # Changed from Set to List

    async def connect(self, websocket: WebSocket) -> None:
        """Connect a new WebSocket client.

        Args:
            websocket: The WebSocket connection to add
        """
        await websocket.accept()
        self.active_connections.append(websocket)  # Changed from add to append
        logger.debug(
            f"WebSocket client connected, total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Disconnect a WebSocket client.

        Args:
            websocket: The WebSocket connection to remove
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(
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


class NekoConf:
    """NekoConf API and Web server for managing configuration."""

    def __init__(
        self,
        config_manager: ConfigManager,
        username: str = "admin",
        password: str = None,
    ) -> None:
        """Initialize the web server.

        Args:
            config_manager: Configuration manager instance
            username: Username for authentication (default: admin)
            password: Password for authentication (if None, authentication is disabled)
        """
        self.config_manager = config_manager
        self.username = username
        self.password = password
        self.security = HTTPBasic()

        # Try to get the static directory using importlib.resources (Python 3.7+)
        self.static_dir = Path(importlib.resources.files("nekoconf") / "static")
        self.templates = Jinja2Templates(directory=str(self.static_dir))

        logger.info(f"Static resources directory set to: {self.static_dir.resolve()}")

        self.app = FastAPI(title="NekoConf", description="Configuration Management API")
        self.ws_manager = WebSocketManager()

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Register as configuration observer
        self.config_manager.register_observer(self._on_config_change)

        # Set up routes
        self._setup_routes()

    def _verify_credentials(self, credentials: HTTPBasicCredentials) -> bool:
        """Verify the provided credentials.

        Args:
            credentials: The HTTP Basic credentials to verify

        Returns:
            True if credentials are valid, False otherwise
        """
        if self.password is None:  # Authentication disabled
            return True

        correct_username = secrets.compare_digest(credentials.username, self.username)
        correct_password = secrets.compare_digest(credentials.password, self.password)
        return correct_username and correct_password

    def _auth_required(
        self, credentials: HTTPBasicCredentials = Depends(HTTPBasic())
    ) -> HTTPBasicCredentials:
        """Dependency for routes that require authentication.

        Args:
            credentials: The HTTP Basic credentials to verify

        Returns:
            The credentials if valid

        Raises:
            HTTPException: If credentials are invalid
        """
        if self.password is None:  # Authentication disabled
            return credentials

        if not self._verify_credentials(credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials

    def _setup_routes(self) -> None:
        """Set up API routes and static file serving."""

        # API endpoints
        @self.app.get("/api/config", response_class=JSONResponse)
        def get_config(credentials: HTTPBasicCredentials = Depends(self._auth_required)):
            """Get the entire configuration."""
            return self.config_manager.get()

        @self.app.get("/api/config/{key_path:path}", response_class=JSONResponse)
        def get_config_path(
            key_path: str, credentials: HTTPBasicCredentials = Depends(self._auth_required)
        ):
            """Get a specific configuration path."""

            # convert key_path to dot notation
            key_path = key_path.replace("/", ".")

            value = self.config_manager.get(key_path)
            if value is None:
                raise HTTPException(status_code=404, detail=f"Path {key_path} not found")
            return value

        @self.app.post("/api/config", response_class=JSONResponse)
        async def update_config(
            data: Dict[str, Any], credentials: HTTPBasicCredentials = Depends(self._auth_required)
        ):
            """Update multiple configuration values."""
            self.config_manager.update(data)

            self.config_manager.save()
            return {"status": "success"}

        @self.app.post("/api/config/reload", response_class=JSONResponse)
        async def reload_config(credentials: HTTPBasicCredentials = Depends(self._auth_required)):
            """Reload configuration from disk."""
            self.config_manager.load()
            return {"status": "success"}

        @self.app.post("/api/config/validate", response_class=JSONResponse)
        async def validate_config(credentials: HTTPBasicCredentials = Depends(self._auth_required)):
            """Validate the current configuration against the schema."""
            errors = self.config_manager.validate()
            if errors:
                return {"valid": False, "errors": errors}
            return {"valid": True}

        @self.app.post("/api/config/{key_path:path}", response_class=JSONResponse)
        async def set_config(
            key_path: str,
            data: Dict[str, Any],
            credentials: HTTPBasicCredentials = Depends(self._auth_required),
        ):
            """Set a specific configuration path."""

            # convert key_path to dot notation
            key_path = key_path.replace("/", ".")

            self.config_manager.set(key_path, data.get("value"))
            self.config_manager.save()
            return {"status": "success"}

        @self.app.delete("/api/config/{key_path:path}", response_class=JSONResponse)
        async def delete_config(
            key_path: str, credentials: HTTPBasicCredentials = Depends(self._auth_required)
        ):
            """Delete a specific configuration path."""
            # convert key_path to dot notation
            key_path = key_path.replace("/", ".")

            if self.config_manager.delete(key_path):
                self.config_manager.save()
                return {"status": "success"}
            else:
                raise HTTPException(status_code=404, detail=f"Path {key_path} not found")

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.ws_manager.connect(websocket)
            try:
                # Send initial configuration
                await websocket.send_json({"type": "config", "data": self.config_manager.get()})

                # Keep the connection open, handle incoming messages
                while True:
                    try:
                        data = await websocket.receive_json()
                        # We could implement commands here later
                        logger.debug(f"Received WebSocket message: {data}")
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON through WebSocket")
            except WebSocketDisconnect:
                self.ws_manager.disconnect(websocket)

        # Serve static files if the directory exists
        if self.static_dir.exists() and self.static_dir.is_dir():
            """Serve static files from the static directory."""

            @self.app.get("/", response_class=HTMLResponse)
            def get_index(
                request: Request, credentials: HTTPBasicCredentials = Depends(self._auth_required)
            ):
                """Serve the main UI page."""
                print(f"Serving index from {self.static_dir.resolve()}")
                return self.templates.TemplateResponse("index.html", {"request": request})

            @self.app.get("/static/script.js")
            def get_script(
                request: Request, credentials: HTTPBasicCredentials = Depends(self._auth_required)
            ):
                return self.templates.TemplateResponse(
                    "script.js", {"request": request}, media_type="application/javascript"
                )

            @self.app.get("/static/styles.css")
            def get_style(
                request: Request, credentials: HTTPBasicCredentials = Depends(self._auth_required)
            ):
                return self.templates.TemplateResponse(
                    "styles.css", {"request": request}, media_type="text/css"
                )

        else:

            @self.app.get("/", response_class=HTMLResponse)
            def get_index(credentials: HTTPBasicCredentials = Depends(self._auth_required)):
                """Serve a basic index page when static files are not available."""
                return HTMLResponse(self._get_index_html())

    async def _on_config_change(self, config_data: Dict[str, Any]) -> None:
        """Handle configuration changes.

        Args:
            config_data: Updated configuration data
        """
        await self.ws_manager.broadcast({"type": "config", "data": config_data})

    def _get_index_html(self) -> str:
        """Generate a basic HTML page when static files are not available.

        Returns:
            HTML content for the index page
        """
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>NekoConf</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 1rem;
                }
                h1 {
                    color: #333;
                    border-bottom: 2px solid #eee;
                    padding-bottom: 0.5rem;
                }
                .error {
                    background: #fff8f8;
                    border-left: 4px solid #dc3545;
                    padding: 1rem;
                    border-radius: 4px;
                }
                code {
                    background: #f5f5f5;
                    padding: 0.2rem 0.4rem;
                    border-radius: 3px;
                    font-size: 0.9em;
                }
            </style>
        </head>
        <body>
            <h1>NekoConf</h1>
            <div class="error">
                <p>The web UI is not available. The static files could not be found.</p>
                <p>Please make sure the static files are properly configured at the correct path.</p>
            </div>
            <h2>API Endpoints</h2>
            <ul>
                <li><code>GET /api/config</code> - Get all configuration</li>
                <li><code>POST /api/config</code> - Update multiple configuration values</li>
                <li><code>GET /api/config/{key}</code> - Get a specific configuration value</li>
                <li><code>PUT /api/config/{key}</code> - Set a specific configuration value</li>
                <li><code>DELETE /api/config/{key}</code> - Delete a specific configuration value</li>
                <li><code>POST /api/config/reload</code> - Reload configuration from disk</li>
                <li><code>POST /api/config/validate</code> - Validate configuration against schema</li>
                <li><code>WebSocket /ws</code> - Real-time configuration updates</li>
            </ul>
        </body>
        </html>
        """

    async def start_background(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        reload: bool = False,
    ):
        """Start the dashboard server in the background."""

        logger.info(f"Starting NekoConf web server at http://{host}:{port} in the background")

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
        logger.info(f"Starting NekoConf web server at http://{host}:{port}")

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_level=logging.INFO,
        )
