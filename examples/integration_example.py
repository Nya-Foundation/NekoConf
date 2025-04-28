#!/usr/bin/env python
"""
Example demonstrating how to integrate NekoConf into another application.
"""

import threading
import time
from pathlib import Path

from nekoconf import NekoConfigClient, NekoConfigManager, NekoConfigServer


class MyApplication:
    """Example application that uses NekoConf for configuration management."""

    def __init__(self, config_path):
        """Initialize the application with a configuration file.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = Path(config_path)

        # Initialize the configuration manager
        self.config_manager = NekoConfigManager(self.config_path)

        # Initialize the configuration API for internal use
        self.config_api = NekoConfigClient(self.config_path)

        # Register for configuration changes
        self.config_api.observe(self.on_config_change)

        # Initialize application state from configuration
        self.update_app_state()

        # Start the web server in a separate thread
        self.web_server = NekoConfigServer(self.config_manager)
        self.server_thread = threading.Thread(
            target=self.web_server.run,
            kwargs={"host": "127.0.0.1", "port": 8000},
            daemon=True,
        )

    def start(self):
        """Start the application."""
        print("Starting application...")

        # Start the web server thread
        self.server_thread.start()
        print("Configuration web server started at http://127.0.0.1:8000")

        # Main application loop
        try:
            while True:
                self.run_application_logic()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")

    def update_app_state(self):
        """Update application state from configuration."""
        config = self.config_api.get_all()

        # Extract configuration values with type-safety
        self.debug_mode = self.config_api.get_bool("server.debug", False)
        self.host = self.config_api.get_str("server.host", "localhost")
        self.port = self.config_api.get_int("server.port", 8080)

        print(
            f"Application configured with: host={self.host}, port={self.port}, debug={self.debug_mode}"
        )

    def on_config_change(self, config_data):
        """Handle configuration changes.

        Args:
            config_data: The updated configuration data
        """
        print("\nConfiguration changed, updating application state...")
        self.update_app_state()

    def run_application_logic(self):
        """Run the main application logic."""
        if self.debug_mode:
            print("Running application in DEBUG mode...")
        # Simulate application work
        pass


def main():
    """Main function to demonstrate the integration."""
    # Create a sample configuration file
    config_path = Path("sample_config.yaml")

    if not config_path.exists():
        # Create a sample configuration file if it doesn't exist
        from nekoconf.core.utils import save_file

        sample_config = {
            "server": {"host": "localhost", "port": 8080, "debug": True},
            "database": {"url": "sqlite:///app.db", "pool_size": 5},
            "logging": {"level": "INFO", "file": "app.log"},
        }

        save_file(config_path, sample_config)
        print(f"Created sample configuration file: {config_path}")

    # Create and start the application
    app = MyApplication(config_path)
    app.start()


if __name__ == "__main__":
    main()
