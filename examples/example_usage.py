#!/usr/bin/env python
"""
Example script demonstrating how to use NekoConf in a Python application.
"""

import time
from pathlib import Path

from nekoconf import ConfigAPI


def on_config_change(config_data):
    """Callback function that will be called when the configuration changes."""
    print("\nConfiguration changed:")
    print(config_data)


def main():
    """Main function demonstrating NekoConf API usage."""
    # Path to the sample configuration file
    config_path = Path(__file__).parent / "sample_config.yaml"

    print(f"Using configuration file: {config_path}")

    # Initialize the ConfigAPI
    config_api = ConfigAPI(config_path)

    # Register the callback to be notified of configuration changes
    config_api.observe(on_config_change)

    print("\nCurrent configuration:")
    print(config_api.get_all())

    # Get specific configuration values
    server_host = config_api.get("server.host")
    server_port = config_api.get("server.port")
    debug_mode = config_api.get("server.debug")

    print(f"\nServer configuration: {server_host}:{server_port} (Debug: {debug_mode})")

    # Get a value with a default
    timeout = config_api.get("server.timeout", 30)
    print(f"Server timeout: {timeout} seconds (default value)")

    print("\nWaiting for configuration changes... (Press Ctrl+C to exit)")
    try:
        # Keep the script running to receive configuration change notifications
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        # Unregister the observer when done
        config_api.stop_observing(on_config_change)


if __name__ == "__main__":
    main()
