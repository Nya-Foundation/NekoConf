"""Remote configuration sync implementation for NekoConf."""

import asyncio
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

# These imports should always succeed because this module is only imported
# when HAS_REMOTE_DEPS is True in __init__.py
import requests
import websocket
from requests.exceptions import RequestException

from ..utils.helper import getLogger


class RemoteConfigClient:
    """Client for syncing configuration with a remote NekoConf server."""

    def __init__(
        self,
        remote_url: str,
        api_key: Optional[str] = None,
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        read_only: bool = True,
        logger: Optional[logging.Logger] = None,
        reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        connect_timeout: float = 5.0,
    ):
        """Initialize the remote configuration sync client.

        Args:
            remote_url: Base URL of the remote NekoConf server (e.g., "https://config.example.com")
            api_key: API key for authentication with the remote server
            on_update: Callback function that will be called when config is updated
            read_only: If True, only read from remote server, no writes allowed
            logger: Optional custom logger
            reconnect_attempts: Number of reconnection attempts on failure
            reconnect_delay: Delay between reconnection attempts (with exponential backoff)
            connect_timeout: Timeout for initial connection
        """
        self.remote_url = remote_url.rstrip("/")
        self.api_key = api_key
        self.on_update = on_update
        self.read_only = read_only
        self.logger = logger or getLogger(__name__)
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.connect_timeout = connect_timeout

        self._ws_url = (
            f"{self.remote_url.replace('http://', 'ws://').replace('https://', 'wss://')}/ws"
        )
        self._api_url = f"{self.remote_url}/api/config"

        self._ws = None
        self._ws_thread = None
        self._running = False
        self._config_data = {}
        self._connected = False
        self._lock = threading.RLock()

    def start(self) -> bool:
        """Start the synchronization with the remote server.

        Returns:
            True if initial connection and config fetch was successful
        """
        # First fetch config via REST API
        if not self._fetch_initial_config():
            self.logger.error("Failed to fetch initial configuration from remote server")
            return False

        # Then start WebSocket connection for real-time updates
        self._start_websocket()
        return True

    def stop(self) -> None:
        """Stop the synchronization with the remote server."""
        self._running = False
        if self._ws:
            self._ws.close()
            self._ws = None

        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=1.0)

    def get_config(self) -> Dict[str, Any]:
        """Get the current configuration from remote server.

        Returns:
            The current configuration data
        """
        with self._lock:
            return self._config_data.copy()

    def update_config_value(self, key: str, value: Any) -> bool:
        """Update a configuration value on the remote server.

        Args:
            key: The configuration key to update
            value: The new value

        Returns:
            True if update was successful, False otherwise
        """
        if self.read_only:
            self.logger.warning("Cannot update config in read-only mode")
            return False

        try:
            headers = self._get_auth_headers()

            url = f"{self._api_url}/{key}"
            response = requests.post(url, json={"value": value}, headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.debug(f"Successfully updated remote config: {key} = {value}")
                return True
            else:
                self.logger.error(
                    f"Failed to update remote config: {key} - Status code: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
        except RequestException as e:
            self.logger.error(f"Error updating remote config: {key} - {str(e)}")
            return False

    def update_config(self, data: Dict[str, Any]) -> bool:
        """Update multiple configuration values on the remote server.

        Args:
            data: Dictionary of configuration values to update

        Returns:
            True if update was successful, False otherwise
        """
        if self.read_only:
            self.logger.warning("Cannot update config in read-only mode")
            return False

        try:
            headers = self._get_auth_headers()

            response = requests.post(self._api_url, json=data, headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.debug("Successfully updated remote config with multiple values")
                return True
            else:
                self.logger.error(
                    f"Failed to update remote config - Status code: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
        except RequestException as e:
            self.logger.error(f"Error updating remote config: {str(e)}")
            return False

    def reload_remote_config(self) -> bool:
        """Trigger a reload of the configuration on the remote server.

        Returns:
            True if successful, False otherwise
        """
        if self.read_only:
            self.logger.warning("Cannot trigger reload in read-only mode")
            return False

        try:
            headers = self._get_auth_headers()

            response = requests.post(f"{self._api_url}/reload", headers=headers, timeout=10)

            if response.status_code == 200:
                self.logger.debug("Successfully triggered config reload on remote server")
                return True
            else:
                self.logger.error(
                    f"Failed to trigger config reload - Status code: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
        except RequestException as e:
            self.logger.error(f"Error triggering config reload: {str(e)}")
            return False

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Dictionary of headers with authentication if API key is set
        """
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            # Follow the proper Bearer token format for Authentication header
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _fetch_initial_config(self) -> bool:
        """Fetch the initial configuration from the remote server.

        Returns:
            True if successful, False otherwise
        """
        try:
            headers = self._get_auth_headers()

            response = requests.get(self._api_url, headers=headers, timeout=self.connect_timeout)

            if response.status_code == 200:
                config_data = response.json()
                with self._lock:
                    self._config_data = config_data

                self.logger.info("Successfully fetched initial configuration from remote server")

                # Call the update callback if provided
                if self.on_update:
                    try:
                        self.on_update(config_data)
                    except Exception as e:
                        self.logger.error(f"Error in update callback: {str(e)}")

                return True
            else:
                self.logger.error(
                    f"Failed to fetch initial config - Status code: {response.status_code}, "
                    f"Response: {response.text}"
                )
                return False
        except RequestException as e:
            self.logger.error(f"Error fetching initial config: {str(e)}")
            return False

    def _start_websocket(self) -> None:
        """Start WebSocket connection for real-time updates."""
        self._running = True

        # Create WebSocket thread
        self._ws_thread = threading.Thread(
            target=self._websocket_thread,
            daemon=True,
            name="NekoConfRemoteSync-WebSocket",
        )
        self._ws_thread.start()

    def _websocket_thread(self) -> None:
        """WebSocket connection thread function."""
        reconnect_count = 0
        current_delay = self.reconnect_delay

        while self._running:
            try:
                # Setup WebSocket with authorization header if API key is provided
                headers = {}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                self._ws = websocket.WebSocketApp(
                    self._ws_url,
                    header=[f"{k}: {v}" for k, v in headers.items()],
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close,
                )

                # Connect to WebSocket server
                self.logger.info(f"Connecting to WebSocket at {self._ws_url}")
                self._ws.run_forever()

                # If we're not running anymore, exit the loop
                if not self._running:
                    break

                # If we get here, the connection was closed, attempt reconnect
                reconnect_count += 1
                if self.reconnect_attempts > 0 and reconnect_count > self.reconnect_attempts:
                    self.logger.error(
                        f"Max reconnection attempts ({self.reconnect_attempts}) reached, giving up"
                    )
                    break

                # Exponential backoff for reconnect
                self.logger.info(
                    f"WebSocket connection closed, reconnecting in {current_delay:.2f}s "
                    f"(attempt {reconnect_count}/{self.reconnect_attempts or 'unlimited'})"
                )

                # Sleep before reconnect
                for _ in range(int(current_delay * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)

                # Increase delay for next reconnect (with cap)
                current_delay = min(current_delay * 2, 60.0)

            except Exception as e:
                self.logger.error(f"Error in WebSocket thread: {str(e)}")
                break

        self.logger.debug("WebSocket thread exiting")

    def _on_ws_open(self, ws):
        """WebSocket open event handler."""
        self.logger.info("WebSocket connection established")
        self._connected = True

    def _on_ws_message(self, ws, message):
        """WebSocket message event handler."""
        try:
            data = json.loads(message)

            if data.get("type") == "update" and "data" in data:
                config_data = data["data"]

                # Update our local copy
                with self._lock:
                    self._config_data = config_data

                self.logger.debug("Received updated configuration from WebSocket")

                # Call the update callback if provided
                if self.on_update:
                    try:
                        self.on_update(config_data)
                    except Exception as e:
                        self.logger.error(f"Error in update callback: {str(e)}")

        except json.JSONDecodeError:
            self.logger.warning("Received invalid JSON from WebSocket")
        except Exception as e:
            self.logger.error(f"Error processing WebSocket message: {str(e)}")

    def _on_ws_error(self, ws, error):
        """WebSocket error event handler."""
        self.logger.error(f"WebSocket error: {str(error)}")

    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket close event handler."""
        self._connected = False
        close_info = f" (code: {close_status_code}, message: {close_msg})" if close_msg else ""
        self.logger.info(f"WebSocket connection closed{close_info}")
