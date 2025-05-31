"""Remote storage backend for NekoConf orchestrator."""

import json
import threading
import time
from typing import Any, Dict, List, Optional

import requests
import websocket

from .base import StorageBackend, StorageError


class RemoteStorageBackend(StorageBackend):
    """Storage backend that syncs configuration with a remote NekoConf orchestrator.

    This backend connects to a specific app on a remote NekoConf orchestrator
    via REST API and WebSocket for real-time updates.
    """

    def __init__(
        self,
        remote_url: str,
        app_name: str = "default",
        api_key: Optional[str] = None,
        reconnect_attempts: int = 20,
        reconnect_delay: float = 1.0,
        connect_timeout: float = 5.0,
        **kwargs,
    ):
        """Initialize the remote storage backend.

        Args:
            remote_url: Base URL of the remote NekoConf orchestrator
            app_name: Name of the app to connect to (default: "default")
            api_key: API key for authentication with the remote server
            reconnect_attempts: Number of reconnection attempts on failure
            reconnect_delay: Delay between reconnection attempts
            connect_timeout: Timeout for initial connection
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)

        self.remote_url = remote_url.rstrip("/")
        self.app_name = app_name
        self.api_key = api_key
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.connect_timeout = connect_timeout

        # Connection state
        self._connected = False

        self._change_callbacks: List[callable] = []

        # API and WebSocket URLs for the specific app
        self._ws_url = f"{self.remote_url.replace('http://', 'ws://').replace('https://', 'wss://')}/ws/{self.app_name}"
        self._api_url = f"{self.remote_url}/api/apps/{self.app_name}/config"
        self._ws = None
        self._ws_thread = None
        self._running = False

        # Auto-connect on initialization
        self._connect()

    def __str__(self):
        return f"{self.__class__.__name__}(remote_url={self.remote_url}, app_name={self.app_name})"

    def set_change_callback(self, callback: callable) -> None:
        """Register a callback to be called on configuration changes.

        Args:
            callback: Function to call when configuration changes
        """
        if callable(callback):
            self._change_callbacks.append(callback)
        else:
            raise ValueError("Callback must be a callable function")

    def unset_change_callback(self, callback: callable) -> None:
        """Unregister a previously set change callback.

        Args:
            callback: Function to remove from the change callbacks
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)
        else:
            raise ValueError("Callback not found in registered callbacks")

    def load(self) -> Dict[str, Any]:
        """Load configuration data from remote orchestrator.

        Returns:
            Dictionary containing the configuration data

        Raises:
            StorageError: If remote loading fails
        """
        if not self._connected:
            raise StorageError("Failed to connect to remote orchestrator")

        try:
            headers = self._set_auth_headers()
            response = requests.get(self._api_url, headers=headers, timeout=self.connect_timeout)

            if response.status_code == 200:
                config_data = response.json()
                self.logger.debug(
                    f"Loaded configuration for app '{self.app_name}' from remote orchestrator"
                )
                return config_data
            elif response.status_code == 404:
                # App doesn't exist, return empty config
                self.logger.warning(f"App '{self.app_name}' not found on remote orchestrator")
                return {}
            else:
                error_msg = f"Failed to load config for app '{self.app_name}': {response.status_code} - {response.text}"
                raise StorageError(error_msg)

        except requests.RequestException as e:
            error_msg = f"Error loading configuration for app '{self.app_name}': {e}"
            self.logger.error(error_msg)
            raise StorageError(error_msg) from e

    def save(self, data: Dict[str, Any]) -> bool:
        """Save configuration data to remote orchestrator.

        Args:
            data: Configuration data to save

        Returns:
            True if save was successful, False otherwise
        """
        if not self._connected and not self._connect():
            return False

        try:
            headers = self._set_auth_headers()
            response = requests.put(self._api_url, json={"data": data}, headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.debug(
                    f"Saved configuration for app '{self.app_name}' to remote orchestrator"
                )
                return True
            elif response.status_code == 404:
                # App doesn't exist, try to create it first
                self.logger.info(f"App '{self.app_name}' not found, attempting to create it")
                if self._create_app(data):
                    return True
                else:
                    self.logger.error(f"Failed to create app '{self.app_name}'")
                    return False
            else:
                self.logger.error(
                    f"Failed to save config for app '{self.app_name}': {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            self.logger.error(f"Error saving configuration for app '{self.app_name}': {e}")
            return False

    def reload(self) -> Dict[str, Any]:
        """Reload configuration from remote orchestrator.

        Returns:
            Dictionary containing the reloaded configuration data
        """

        return self.load()

    def cleanup(self) -> None:
        """Clean up resources used by the remote storage backend."""
        self._running = False
        if self._ws:
            self._ws.close()
            self._ws = None

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=1.0)

        self.logger.debug(f"Remote storage backend for app '{self.app_name}' cleaned up")

    def _create_app(self, initial_data: Dict[str, Any]) -> bool:
        """Create the app on the remote orchestrator.

        Args:
            initial_data: Initial configuration data for the app

        Returns:
            True if app was created successfully, False otherwise
        """
        try:

            payload = {
                "name": self.app_name,
                "data": initial_data,
            }

            headers = self._set_auth_headers()
            app_create_url = f"{self.remote_url}/api/apps/{self.app_name}"
            response = requests.post(app_create_url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.info(
                    f"Successfully created app '{self.app_name}' on remote orchestrator"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to create app '{self.app_name}': {response.status_code} - {response.text}"
                )
                return False

        except requests.RequestException as e:
            self.logger.error(f"Error creating app '{self.app_name}': {e}")
            return False

    def _connect(self) -> bool:
        """Establish connection to remote orchestrator.

        Returns:
            True if connection was successful, False otherwise
        """
        try:
            self._connected = True

            # Start WebSocket for real-time updates
            self._start_websocket()

            self.logger.info(
                f"Connected to remote orchestrator: {self.remote_url} (app: {self.app_name})"
            )
            return True

        except Exception as e:
            self.logger.error(
                f"Failed to connect to remote orchestrator for app '{self.app_name}': {e}"
            )
            return False

    def _set_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        if self._ws_thread and self._ws_thread.is_alive():
            return  # Already running

        self._running = True
        self._ws_thread = threading.Thread(
            target=self._websocket_thread, daemon=True, name=f"NekoConf-RemoteSync-{self.app_name}"
        )
        self._ws_thread.start()

    def _websocket_thread(self) -> None:
        """WebSocket connection thread function."""
        reconnect_count = 0
        current_delay = self.reconnect_delay

        while self._running:
            try:
                headers = self._set_auth_headers()
                self._ws = websocket.WebSocketApp(
                    self._ws_url,
                    header=headers,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )

                self.logger.debug(
                    f"Connecting to WebSocket for app '{self.app_name}': {self._ws_url}"
                )
                self._ws.run_forever()

                if not self._running:
                    break

                # Handle reconnection
                reconnect_count += 1
                if self.reconnect_attempts > 0 and reconnect_count > self.reconnect_attempts:
                    self.logger.error(
                        f"Max reconnection attempts reached for app '{self.app_name}', giving up"
                    )
                    break

                self.logger.info(
                    f"Reconnecting to app '{self.app_name}' in {current_delay:.1f}s (attempt {reconnect_count})"
                )
                time.sleep(current_delay)
                current_delay = min(current_delay * 2, 60.0)

            except Exception as e:
                self.logger.error(f"WebSocket error for app '{self.app_name}': {e}")
                break

    def _on_ws_open(self, ws):
        """WebSocket open event handler."""
        self.logger.debug(f"WebSocket connection established for app '{self.app_name}'")

    def _on_ws_message(self, ws, message):
        """WebSocket message event handler."""
        try:
            data: dict = json.loads(message)
            self.logger.debug(f"Received WebSocket message for app '{self.app_name}': {data}")
            if data.get("type") == "update" and "data" in data:
                config_data = data["data"]

                self.logger.debug(
                    f"Received config update for app '{self.app_name}' from WebSocket"
                )

                # Notify NekoConf of the change
                if self._change_callbacks:
                    try:
                        for callback in self._change_callbacks:
                            callback(config_data=config_data)
                            self.logger.debug(
                                f"Called change callback {callback.__name__} for app '{self.app_name}'"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error in change callback for app '{self.app_name}': {e}"
                        )

        except (json.JSONDecodeError, Exception) as e:
            self.logger.warning(
                f"Error processing WebSocket message for app '{self.app_name}': {e}"
            )

    def _on_ws_error(self, ws, error):
        """WebSocket error event handler."""
        self.logger.error(f"WebSocket error for app '{self.app_name}': {error}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket close event handler."""
        self.logger.debug(
            f"WebSocket closed for app '{self.app_name}': {close_status_code} - {close_msg}"
        )
