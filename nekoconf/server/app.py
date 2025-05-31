"""Configuration orchestrator for NekoConf.

An elegant, modular web interface for managing multiple configuration instances
with real-time updates and intuitive APIs.
"""

import asyncio
import importlib.resources
import json
import logging
import re
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator

from nekoconf._version import __version__
from nekoconf.core.config import NekoConf
from nekoconf.utils.helper import getLogger, load_string

from .auth import AuthMiddleware, NekoAuthGuard


class InvalidConfigDataError(Exception):
    """Custom exception for invalid configuration data."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# Configuration formats supported
SUPPORTED_FORMATS: Set[str] = {"json", "yaml", "toml"}

# Valid types for configuration values
VALID_TYPES: Set[str] = {"str", "int", "float", "bool", "list", "dict"}


class ConfigRequest(BaseModel):
    """Request model for configuration operations."""

    data: str = Field(..., description="Configuration data as string")
    format: str = Field(default="json", description="Configuration format")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        """Validate configuration format."""
        if v not in SUPPORTED_FORMATS:
            raise ValueError(f"Format must be one of: {', '.join(SUPPORTED_FORMATS)}")
        return v

    model_config = ConfigDict(
        json_schema_extra={"example": {"data": '{"key": "value"}', "format": "json"}}
    )


class AppCreateRequest(BaseModel):
    """Request model for creating a new app."""

    name: str = Field(..., min_length=1, max_length=64, description="App name")
    description: Optional[str] = Field(None, max_length=256, description="Optional app description")
    data: str = Field(default="{}", description="Initial configuration data")
    format: str = Field(default="json", description="Configuration format")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate app name format."""
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", v):
            raise ValueError(
                "Name must start with alphanumeric and contain only "
                "alphanumeric, underscore, or hyphen characters"
            )
        return v

    @field_validator("format")
    @classmethod
    def validate_format(cls, v):
        """Validate configuration format."""
        if v not in SUPPORTED_FORMATS:
            raise ValueError(f"Format must be one of: {', '.join(SUPPORTED_FORMATS)}")
        return v


class ConfigPathUpdateRequest(BaseModel):
    """Request model for updating a specific configuration path."""

    value: Any = Field(..., description="Value to set at the configuration path")
    type: str = Field(default="str", description="Type hint for the value")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        """Validate value type."""
        if v.lower() not in VALID_TYPES:
            raise ValueError(f"Type must be one of: {', '.join(VALID_TYPES)}")
        return v.lower()


class AppUpdateMetadataRequest(BaseModel):
    """Request model for updating app metadata (name and description)."""

    name: Optional[str] = Field(None, min_length=1, max_length=64, description="New app name")
    description: Optional[str] = Field(None, max_length=256, description="New app description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        """Validate app name format."""
        if v is not None and not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", v):
            raise ValueError(
                "Name must start with alphanumeric and contain only "
                "alphanumeric, underscore, or hyphen characters"
            )
        return v


class ConfigApp:
    """Represents a single configuration app with its associated resources."""

    def __init__(
        self,
        name: str,
        config: NekoConf,
        description: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.name = name
        self.description = description
        self.config = config
        self.logger = logger or getLogger(__name__)
        self.last_modified = None
        self.ws_manager = WebSocketManager(name, self.logger)
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for real-time updates."""

        if self.config.event_disabled:
            return

        from nekoconf.event.pipeline import EventType

        self.config.event_pipeline.register_handler(
            self._on_config_change,
            event_types=[EventType.CHANGE],
            path_pattern="@global",
            priority=100,
        )

    async def _on_config_change(
        self,
        **kwargs,
    ) -> None:
        """Handle configuration changes and notify WebSocket clients."""
        await self.ws_manager.broadcast({"type": "update", "data": self.config.get_all()})

    def cleanup(self) -> None:
        """Clean up app resources."""
        self.config.cleanup()
        self.ws_manager.cleanup()

    @property
    def info(self) -> Dict[str, Any]:
        """Get app information summary."""
        return {
            "name": self.name,
            "description": self.description,
            "config_count": len(self.config.get_all()),
            "last_modified": self.last_modified,
            "status": "active",
            "connections": len(self.ws_manager.connections),
        }


class WebSocketManager:
    """Elegant WebSocket connection manager for real-time updates."""

    def __init__(self, app_name: str, logger: Optional[logging.Logger] = None):
        self.app_name = app_name
        self.logger = logger or getLogger(__name__)
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.connections.append(websocket)
        self.logger.debug(
            f"WebSocket connected to '{self.app_name}' ({len(self.connections)} total)"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.connections:
            self.connections.remove(websocket)
            self.logger.debug(
                f"WebSocket disconnected from '{self.app_name}' "
                f"({len(self.connections)} remaining)"
            )

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast message to all connected clients."""
        if not self.connections:
            return

        failed_connections = []
        for websocket in self.connections[:]:  # Create a copy to iterate safely
            try:
                self.logger.debug(f"Broadcasting message to WebSocket ({websocket.client})")
                await websocket.send_json(message)
            except Exception as e:
                self.logger.warning(f"Failed to send to WebSocket: {e}")
                failed_connections.append(websocket)

        # Clean up failed connections
        for websocket in failed_connections:
            self.disconnect(websocket)

    def cleanup(self) -> None:
        """Close all connections gracefully."""
        for websocket in self.connections[:]:
            try:
                asyncio.create_task(websocket.close())
            except Exception:
                pass
        self.connections.clear()


class AppManager:
    """Elegant manager for multiple NekoConf app instances."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or getLogger(__name__)
        self.apps: Dict[str, ConfigApp] = {}

    def create_app(
        self,
        name: str,
        config: Optional[NekoConf] = None,
        description: Optional[str] = None,
    ) -> ConfigApp:
        """Create a new configuration app."""
        if not self._is_valid_name(name):
            raise ValueError(f"Invalid app name: {name}")

        if name in self.apps:
            raise ValueError(f"App '{name}' already exists")

        # Create NekoConf instance if not provided
        if config is None:
            default = self._get_default_data()
            config = NekoConf(default, event_emission_enabled=True)

        app = ConfigApp(name, config, description, self.logger)
        self.apps[name] = app

        self.logger.info(f"Created app: {name}")
        return app

    def get_app(self, name: str) -> Optional[ConfigApp]:
        """Get an app by name."""
        return self.apps.get(name)

    def delete_app(self, name: str) -> bool:
        """Delete an app and clean up its resources."""
        if name not in self.apps:
            return False

        self.apps[name].cleanup()
        del self.apps[name]

        self.logger.info(f"Deleted app: {name}")
        return True

    def update_app_metadata(
        self, current_name: str, new_name: Optional[str] = None, description: Optional[str] = None
    ) -> bool:
        """Update app metadata (name and/or description)."""
        if current_name not in self.apps:
            return False

        app = self.apps[current_name]

        # Update description if provided
        if description is not None:
            app.description = description

        if new_name is not None and new_name != current_name:
            if not self._is_valid_name(new_name):
                raise ValueError(f"Invalid app name: {new_name}")

            if new_name in self.apps:
                raise ValueError(f"App '{new_name}' already exists")

            # Update app name
            app.name = new_name
            app.ws_manager.app_name = new_name

            # Move app in the registry
            self.apps[new_name] = app
            del self.apps[current_name]

            self.logger.info(f"Renamed app: {current_name} -> {new_name}")

        self.logger.info(f"Updated app metadata: {app.name}")
        return True

    def list_apps(self) -> List[str]:
        """List all app names."""
        return list(self.apps.keys())

    def get_apps_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all apps."""
        return {name: app.info for name, app in self.apps.items()}

    async def broadcast_to_app(self, name: str, message: Dict[str, Any]) -> bool:
        """Broadcast message to all clients of a specific app."""
        app = self.apps.get(name)
        if app:
            await app.ws_manager.broadcast(message)
            return True
        return False

    def cleanup(self) -> None:
        """Clean up all apps and resources."""
        for name in list(self.apps.keys()):
            self.delete_app(name)

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Validate app name format."""
        if not name or len(name) > 64:
            return False
        return re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$", name) is not None

    @staticmethod
    def _get_default_data() -> Dict[str, Any]:
        """Get default data for app initialization."""
        return {
            "server": {
                "host": "localhost",
                "port": 8080,
                "debug": True,
                "options": {"timeout": 30, "retries": 3},
            },
            "database": {
                "host": "localhost",
                "port": 5432,
                "name": "test_db",
                "credentials": {"username": "test_user", "password": "test_pass"},
            },
            "logging": {"level": "INFO", "file": "app.log"},
        }


class NekoConfOrchestrator:
    """Elegant configuration orchestrator for managing multiple NekoConf instances."""

    def __init__(
        self,
        apps: Union[Dict[str, NekoConf], NekoConf, None] = None,
        api_key: Optional[str] = None,
        read_only: bool = False,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the configuration orchestrator.

        Args:
            apps: Optional dictionary of app_name -> NekoConf instances
            api_key: Optional API key for authentication
            read_only: If True, disables write operations
            logger: Optional logger instance
        """
        self.read_only = read_only
        self.logger = logger or getLogger(__name__)

        # Initialize components
        self.manager = AppManager(self.logger)
        self.auth = NekoAuthGuard(api_key=api_key) if api_key else None

        # Add initial apps if provided
        if apps:
            if isinstance(apps, NekoConf):
                apps = {"default": apps}
            for app_name, config in apps.items():
                self.manager.create_app(name=app_name, config=config)

        else:
            # Create a default app with example configuration
            default_config = AppManager._get_default_data()
            config = NekoConf(default_config, event_emission_enabled=True)
            self.manager.create_app(name="default", config=config)

        # Setup FastAPI application
        self._setup_web_resources()
        self.app = self._create_fastapi_app()
        self._setup_middleware()
        self._setup_routes()

    def _setup_web_resources(self) -> None:
        """Setup web resource directories and templates."""
        self.www_dir = Path(importlib.resources.files("nekoconf.server") / "html")
        self.static_dir = self.www_dir / "static"
        if self.www_dir.exists():
            self.templates = Jinja2Templates(directory=str(self.www_dir))

    def _create_fastapi_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            self.logger.info("Starting NekoConf orchestrator...")
            yield
            self.logger.info("Shutting down NekoConf orchestrator...")
            self.manager.cleanup()

        return FastAPI(
            title="NekoConf Orchestrator",
            description="Elegant multi-app configuration management orchestrator",
            version=__version__,
            lifespan=lifespan,
        )

    def _setup_middleware(self) -> None:
        """Setup middleware for the FastAPI application."""
        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Authentication middleware
        if self.auth:
            self.app.add_middleware(AuthMiddleware, auth=self.auth, logger=self.logger)

    def _setup_routes(self) -> None:
        """Setup all API routes in a modular way."""
        self._setup_health_routes()
        self._setup_app_routes()
        self._setup_config_routes()
        self._setup_websocket_routes()
        self._setup_static_routes()

    def _setup_health_routes(self) -> None:
        """Setup health check routes."""

        @self.app.get("/health")
        def health_check():
            """Health check endpoint."""
            return {
                "status": "ok",
                "version": __version__,
                "apps": len(self.manager.apps),
                "read_only": self.read_only,
            }

    def _setup_app_routes(self) -> None:
        """Setup app management routes."""

        @self.app.get("/api/apps")
        async def list_apps():
            """List all managed apps with their information."""
            return {"data": self.manager.get_apps_info()}

        @self.app.get("/api/apps/{app_name}")
        async def get_app_info(app_name: str):
            """Get information about a specific app."""
            app = self._get_app_or_404(app_name)
            return {"data": app.info}

        @self.app.post("/api/apps", status_code=status.HTTP_201_CREATED)
        async def create_app(request: AppCreateRequest):
            """Create a new configuration app."""
            try:
                # Parse configuration data
                config_data = self._parse_config_data(request.data, request.format)
                config = NekoConf(config_data, event_emission_enabled=True)

                # Create the app
                self.manager.create_app(request.name, config, description=request.description)

                return {
                    "message": f"App '{request.name}' created successfully",
                    "name": request.name,
                }

            except InvalidConfigDataError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                self.logger.error(f"Error creating app {request.name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create app: {str(e)}",
                )

        @self.app.put("/api/apps/{app_name}")
        async def update_app(app_name: str, request: AppCreateRequest):
            """Update an existing app's configuration."""
            self._check_readonly()
            app = self._get_app_or_404(app_name)

            try:
                # Parse configuration data
                config_data = self._parse_config_data(request.data, request.format)
                app.config.replace(config_data)
                app.config.save()

                success = self.manager.update_app_metadata(
                    current_name=app_name, new_name=request.name, description=request.description
                )

                # Get the updated app info
                final_name = request.name if request.name else app_name
                app = self.manager.get_app(final_name)

                return {
                    "message": "App metadata updated successfully",
                    "app": app.info if app else None,
                }

            except InvalidConfigDataError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                self.logger.error(f"Error updating app {app_name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update app: {str(e)}",
                )

        @self.app.patch("/api/apps/{app_name}/metadata")
        async def update_app_metadata(app_name: str, request: AppUpdateMetadataRequest):
            """Update app metadata (name and/or description)."""
            self._check_readonly()

            try:
                success = self.manager.update_app_metadata(
                    current_name=app_name, new_name=request.name, description=request.description
                )

                if not success:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail=f"App '{app_name}' not found"
                    )

                # Get the updated app info
                final_name = request.name if request.name else app_name
                app = self.manager.get_app(final_name)

                return {
                    "message": "App metadata updated successfully",
                    "app": app.info if app else None,
                }

            except ValueError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                self.logger.error(f"Error updating app metadata for {app_name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update app metadata: {str(e)}",
                )

        @self.app.delete("/api/apps/{app_name}")
        async def delete_app(app_name: str):
            """Delete an app and clean up its resources."""
            if not self.manager.delete_app(app_name):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"App '{app_name}' not found"
                )

            return {"message": f"App '{app_name}' deleted successfully"}

    def _setup_config_routes(self) -> None:
        """Setup configuration management routes."""

        @self.app.get("/api/apps/{app_name}/config")
        async def get_app_config(app_name: str):
            """Get configuration for a specific app."""
            app = self._get_app_or_404(app_name)
            return app.config.get_all()

        @self.app.put("/api/apps/{app_name}/config")
        async def update_app_config(app_name: str, request: ConfigRequest):
            """Update configuration for a specific app."""
            self._check_readonly()
            app = self._get_app_or_404(app_name)

            try:
                config = self._parse_config_data(request.data, request.format)
                app.config.replace(config)
                app.config.save()

                return {"message": "Configuration updated successfully", "data": config}

            except InvalidConfigDataError as e:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
            except Exception as e:
                self.logger.error(f"Error updating config for {app_name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to update configuration: {str(e)}",
                )

        @self.app.get("/api/apps/{app_name}/config/{path:path}")
        async def get_config_path(app_name: str, path: str):
            """Get a specific configuration path."""
            app = self._get_app_or_404(app_name)

            try:
                value = app.config.get(path, "DOES_NOT_EXIST")
                if value != "DOES_NOT_EXIST":
                    return {"path": path, "value": value}

                raise KeyError(f"Configuration path '{path}' not found")
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Configuration path '{path}' not found",
                )

        @self.app.put("/api/apps/{app_name}/config/{path:path}")
        async def set_config_path(app_name: str, path: str, request: ConfigPathUpdateRequest):
            """Set a specific configuration path."""
            self._check_readonly()
            app = self._get_app_or_404(app_name)

            try:
                value = self._convert_value(request.value, request.type)
                app.config.set(path, value)
                app.config.save()
                return {
                    "message": f"Set {path} = {value}",
                    "path": path,
                    "value": value,
                }

            except Exception as e:
                self.logger.error(f"Error setting {path} for {app_name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to set configuration: {str(e)}",
                )

        @self.app.delete("/api/apps/{app_name}/config/{path:path}")
        async def delete_config_path(app_name: str, path: str):
            """Delete a specific configuration path."""
            self._check_readonly()
            app = self._get_app_or_404(app_name)

            try:
                delete_success = app.config.delete(path)

                if delete_success:
                    app.config.save()
                    return {"message": f"Deleted configuration path: {path}"}

                raise KeyError(f"Configuration path '{path}' not found")

            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Configuration path '{path}' not found",
                )
            except Exception as e:
                self.logger.error(f"Error deleting {path} for {app_name}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete configuration: {str(e)}",
                )

        @self.app.post("/api/apps/{app_name}/validate")
        async def validate_config(app_name: str, request: ConfigRequest):
            """Validate configuration for a specific app."""
            app = self._get_app_or_404(app_name)

            try:
                config = self._parse_config_data(request.data, request.format)
                errors = app.config.validate_schema(config)

                return {
                    "valid": len(errors) == 0,
                    "errors": errors,
                    "data": app.config.get_all(),
                }
            except InvalidConfigDataError as e:
                return {
                    "valid": False,
                    "errors": [f"Invalid content for {request.format} format: {str(e)}"],
                    "data": app.config.get_all(),
                }
            except Exception as e:
                return {
                    "valid": False,
                    "errors": [f"Configuration validation failed: {str(e)}"],
                    "data": app.config.get_all(),
                }

    def _setup_websocket_routes(self) -> None:
        """Setup WebSocket routes for real-time updates."""

        @self.app.websocket("/ws/{app_name}")
        async def websocket_endpoint(websocket: WebSocket, app_name: str):
            """WebSocket endpoint for real-time app updates."""
            app = self.manager.get_app(app_name)
            if not app:
                await websocket.close(code=4004, reason=f"App '{app_name}' not found")
                return

            try:
                await app.ws_manager.connect(websocket)

                # Send initial configuration
                await websocket.send_json({"type": "initial_config", "data": app.config.get_all()})

                # Keep connection alive and handle incoming messages
                while True:
                    try:
                        data = await websocket.receive_text()
                        self.logger.debug(f"Received WebSocket message for {app_name}: {data}")
                    except WebSocketDisconnect:
                        break

            except Exception as e:
                self.logger.error(f"WebSocket error for {app_name}: {e}")
            finally:
                app.ws_manager.disconnect(websocket)

    def _setup_static_routes(self) -> None:
        """Setup static file serving routes."""
        if not self.www_dir.exists():
            return

        @self.app.get("/", response_class=HTMLResponse)
        async def serve_dashboard(request: Request):
            """Serve the orchestrator dashboard."""
            return self._serve_html_file("index.html", request)

        @self.app.get("/favicon.ico")
        async def serve_favicon():
            """Serve favicon."""
            try:
                favicon_path = importlib.resources.files("nekoconf.server.html") / "favicon.ico"
                return FileResponse(favicon_path)
            except Exception:
                return Response(status_code=status.HTTP_404_NOT_FOUND)

        @self.app.get("/{app_name}", response_class=HTMLResponse)
        async def serve_app_config(request: Request, app_name: str):
            """Serve the configuration page for a specific app."""
            if not self.manager.get_app(app_name):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"App '{app_name}' not found"
                )

            return self._serve_html_file("config.html", request)

        @self.app.get("/static/{file_path:path}")
        async def serve_static(file_path: str):
            """Serve static files."""
            try:
                static_file_path = (
                    importlib.resources.files("nekoconf.server.html.static") / file_path
                )
                if static_file_path.is_file():
                    return FileResponse(static_file_path)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
            except Exception as e:
                self.logger.error(f"Error serving static file {file_path}: {e}")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Helper methods
    def _get_app_or_404(self, app_name: str) -> ConfigApp:
        """Get app or raise 404 if not found."""
        app = self.manager.get_app(app_name)
        if not app:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"App '{app_name}' not found"
            )
        return app

    def _parse_config_data(self, data: str, format: str) -> Dict[str, Any]:
        """Parse configuration data from string."""
        try:
            return load_string(data, format)
        except Exception as e:
            raise InvalidConfigDataError(f"Invalid {format} format: {str(e)}")

    def _convert_value(self, value: Any, type_hint: str) -> Any:
        """Convert value to the specified type."""
        type_map = {
            "int": int,
            "float": float,
            "bool": bool,
            "str": str,
            "list": lambda x: json.loads(x) if isinstance(x, str) else list(x),
            "dict": lambda x: json.loads(x) if isinstance(x, str) else dict(x),
        }

        converter = type_map.get(type_hint)
        if not converter:
            raise ValueError(f"Unsupported type: {type_hint}")

        return converter(value)

    def _serve_html_file(self, filename: str, request: Request) -> HTMLResponse:
        """Serve HTML file with template replacement."""
        try:
            with importlib.resources.open_text("nekoconf.server.html", filename) as f:
                html_content = f.read()
                html_content = html_content.replace(
                    "{{ root_path }}",
                    request.scope.get("root_path", ""),
                )
            return HTMLResponse(html_content)
        except Exception as e:
            self.logger.error(f"Error serving {filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to load {filename}",
            )

    def _check_readonly(self) -> None:
        """Check if server is in read-only mode and raise exception if so."""
        if self.read_only:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Server is in read-only mode"
            )

    def run(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
        """Run the orchestrator server."""
        self.logger.info(f"Starting NekoConf Orchestrator at http://{host}:{port}")

        try:
            config = uvicorn.Config(app=self.app, host=host, port=port, reload=reload)
            server = uvicorn.Server(config)
            server.run()
        except KeyboardInterrupt:
            self.logger.info("Server interrupted")
        except Exception as e:
            self.logger.error(f"Server error: {e}")
        finally:
            self.manager.cleanup()
            self.logger.info("Server stopped")
