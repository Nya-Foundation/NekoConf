#!/usr/bin/env python
"""
Example demonstrating how to use NekoConf with async/await in a Python application.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from nekoconf import ConfigAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def on_config_change_async(config_data):
    """Async callback function that will be called when the configuration changes."""
    logger.info("Configuration changed (async notification):")
    # Simulate some async processing
    await asyncio.sleep(0.5)
    logger.info(f"Processed config update: {config_data}")


def on_config_change_sync(config_data):
    """Sync callback function that will be called when the configuration changes."""
    logger.info("Configuration changed (sync notification):")
    logger.info(f"Received: {config_data}")


async def periodic_config_check(config_api, interval=5):
    """Periodically check and log specific configuration values."""
    while True:
        host = config_api.get_str("server.host")
        port = config_api.get_int("server.port")
        debug = config_api.get_bool("server.debug")

        logger.info(f"Current server config: {host}:{port} (Debug: {debug})")

        # Optional: Check if a specific feature flag is enabled
        metrics_enabled = config_api.get_bool("features.enable_metrics", False)
        if metrics_enabled:
            logger.info("Metrics collection is enabled")

        await asyncio.sleep(interval)


async def main():
    """Main async function demonstrating NekoConf API usage."""
    # Path to the sample configuration file
    config_path = Path(__file__).parent / "sample_config.yaml"

    logger.info(f"Using configuration file: {config_path}")

    # Initialize the ConfigAPI
    config_api = ConfigAPI(config_path)

    # Register both sync and async callbacks
    config_api.observe(on_config_change_async)
    config_api.observe(on_config_change_sync)

    logger.info("Current configuration:")
    logger.info(config_api.get_all())

    # Get specific configuration values with type safety
    server_host = config_api.get_str("server.host")
    server_port = config_api.get_int("server.port")
    debug_mode = config_api.get_bool("server.debug")

    logger.info(f"Server configuration: {server_host}:{server_port} (Debug: {debug_mode})")

    # Type-safe access with defaults
    timeout = config_api.get_int("server.timeout", 30)
    logger.info(f"Server timeout: {timeout} seconds (default value)")

    # Start background task to periodically check config
    check_task = asyncio.create_task(periodic_config_check(config_api))

    # Setup clean shutdown
    loop = asyncio.get_running_loop()

    def signal_handler():
        logger.info("Shutdown signal received, cleaning up...")
        check_task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("Application running - press Ctrl+C to exit")
    logger.info("Any changes to the configuration file will be detected automatically")

    try:
        # Keep the script running to receive configuration change notifications
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Main task cancelled")
    finally:
        # Unregister the observers when done
        config_api.stop_observing(on_config_change_async)
        config_api.stop_observing(on_config_change_sync)
        logger.info("Observers unregistered, exiting...")


if __name__ == "__main__":
    asyncio.run(main())
