"""Command-line interface for NekoConf.

This module provides a command-line interface for starting the web server
and performing basic configuration operations.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

from nekoconf import HAS_REMOTE_DEPS, HAS_SCHEMA_DEPS, HAS_SERVER_DEPS
from nekoconf._version import __version__
from nekoconf.core.config import NekoConfigManager
from nekoconf.utils.helper import getLogger, load_file, parse_value, save_file

if HAS_SERVER_DEPS:
    from nekoconf.server import NekoConfigServer

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


from .parser import (
    add_command,
    add_format_param,
    add_in_memory_param,
    add_read_only_param,
    add_remote_params,
    add_schema_param,
)


def _create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        The configured argument parser
    """
    parser = argparse.ArgumentParser(description="NekoConf - Configuration management with web UI")
    parser.add_argument("--version", action="store_true", help="Show version information and exit")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = add_command(subparsers, "server", "Start the configuration web server")
    server_parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to run the server on (default: 0.0.0.0)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )
    add_schema_param(server_parser)
    server_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload for development"
    )
    server_parser.add_argument(
        "--read-only", action="store_true", help="Start server in read-only mode"
    )
    server_parser.add_argument(
        "--api-key",
        type=str,
        help="API key for securing the server (if not set, authentication is disabled)",
    )

    # Get command
    get_parser = add_command(subparsers, "get", "Get a configuration value")
    get_parser.add_argument(
        "key",
        type=str,
        nargs="?",
        help="Configuration key to retrieve (if omitted, returns all)",
    )
    add_format_param(get_parser)
    add_remote_params(get_parser)
    add_in_memory_param(get_parser)

    # Set command
    set_parser = add_command(subparsers, "set", "Set a configuration value")
    set_parser.add_argument("key", type=str, help="Configuration key to set")
    set_parser.add_argument("value", type=str, help="Value to set for the key")
    add_schema_param(set_parser)
    add_remote_params(set_parser)
    add_read_only_param(set_parser)
    add_in_memory_param(set_parser)

    # Delete command
    delete_parser = add_command(subparsers, "delete", "Delete a configuration value")
    delete_parser.add_argument("key", type=str, help="Configuration key to delete")
    add_schema_param(delete_parser)
    add_remote_params(delete_parser)
    add_read_only_param(delete_parser)
    add_in_memory_param(delete_parser)

    # Import command
    import_parser = add_command(
        subparsers, "import", "Import configuration from a file", add_config=False
    )

    # Override default config behavior for import - make it required
    import_parser.add_argument(
        "--config",
        "-c",
        type=str,
        required=True,
        help="Path to the target configuration file (YAML, JSON, or TOML)",
    )
    import_parser.add_argument(
        "import_file",
        type=str,
        help="File to import (YAML, JSON, or TOML)",
    )

    add_schema_param(import_parser)
    add_remote_params(import_parser)
    add_read_only_param(import_parser)
    add_in_memory_param(import_parser)

    # Validate command
    validate_parser = add_command(subparsers, "validate", "Validate configuration against a schema")
    validate_parser.add_argument(
        "--schema",
        "-s",
        type=str,
        required=True,
        help="Path to the schema file (YAML, JSON, or TOML)",
    )
    add_remote_params(validate_parser)
    add_in_memory_param(validate_parser)

    # Init command
    init_parser = add_command(
        subparsers, "init", "Create a new empty configuration file", add_config=False
    )
    init_parser.add_argument(
        "--template",
        "-t",
        type=str,
        help="Template file to use (optional)",
    )

    # Connect command
    connect_parser = subparsers.add_parser("connect", help="Connect to a remote NekoConf server")
    connect_parser.add_argument(
        "remote_url",
        type=str,
        help="URL of the remote NekoConf server (e.g., 'http://config-server:8000')",
    )
    connect_parser.add_argument(
        "--api-key",
        type=str,
        help="API key for authentication with the remote server",
    )
    connect_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to save configuration locally (if not specified, uses in-memory mode)",
    )
    connect_parser.add_argument(
        "--read-only",
        action="store_true",
        default=True,
        help="Use read-only mode (default: True)",
    )
    connect_parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch for configuration changes and print updates",
    )
    add_format_param(connect_parser)

    return parser


def handle_server_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'server' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.server", level="INFO")

    # Check if server dependencies are available
    if not HAS_SERVER_DEPS:
        logger.error(
            "Server features require additional dependencies. "
            "Install them with: pip install nekoconf[server]"
        )
        return 1

    try:
        logger.info(f"Starting NekoConf server version {__version__}")

        config_path = Path(args.config)
        schema_path = Path(args.schema) if args.schema else None

        # Create config manager
        config_manager = NekoConfigManager(config_path, schema_path, logger=logger)
        config_manager.load()

        # Create and run web server
        server = NekoConfigServer(
            config=config_manager,
            api_key=args.api_key,
            read_only=args.read_only,
            logger=logger,
        )
        server.run(host=args.host, port=args.port, reload=args.reload)

        return 0
    except Exception as e:
        if logger.level == logging.DEBUG:
            import traceback

            traceback.print_exc()
        else:
            logger.error(f"Error starting server: {e}.")
        return 1


def _create_config_manager_from_args(
    args: argparse.Namespace, logger: logging.Logger
) -> NekoConfigManager:
    """Create a config manager from command line arguments.

    Args:
        args: Command line arguments
        logger: Logger instance

    Returns:
        Configured NekoConfigManager instance
    """
    schema_path = Path(args.schema) if hasattr(args, "schema") and args.schema else None

    # Check for remote configuration parameters
    remote_url = getattr(args, "remote_url", None)
    remote_api_key = getattr(args, "remote_api_key", None)
    remote_read_only = getattr(args, "remote_read_only", True)
    in_memory = getattr(args, "in_memory", False)

    # Determine config path (might be None if in_memory mode)
    config_path = None
    if hasattr(args, "config") and args.config is not None:
        config_path = Path(args.config)

    # Create the config manager with appropriate settings
    return NekoConfigManager(
        config_path=config_path,
        schema_path=schema_path,
        logger=logger,
        remote_url=remote_url,
        remote_api_key=remote_api_key,
        remote_read_only=remote_read_only,
        in_memory=in_memory,
    )


def _format_output(value: Any, format_type: str) -> str:
    """Format the output according to the specified format.

    Args:
        value: The value to format
        format_type: Format type (json, yaml, raw)

    Returns:
        Formatted string
    """
    if format_type == "json":
        return json.dumps(value, indent=2)
    elif format_type == "yaml":
        if not HAS_YAML:
            raise ImportError("YAML formatting requires pyyaml package.")
        return yaml.dump(value, default_flow_style=False, sort_keys=False)
    else:  # raw format
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)


def _print_formatted(value: Any, format_type: str) -> None:
    """Print the value with the specified format.

    Args:
        value: The value to print
        format_type: Format type (json, yaml, raw)
    """
    print(_format_output(value, format_type))


def _validate_and_save(
    config_manager: NekoConfigManager,
    schema_path: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Validate the configuration and save it if valid.

    Args:
        config_manager: The config manager instance
        schema_path: Optional schema path for validation
        logger: Optional logger instance

    Returns:
        True if validation passed and save was successful
    """
    logger = logger or getLogger(__name__)

    # Validate if schema is provided
    if schema_path:
        errors = config_manager.validate()
        if errors:
            logger.error("Validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return False

    # Save configuration
    return config_manager.save()


def handle_get_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'get' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.get", level="INFO")

    try:
        # Create config manager with potential remote connection
        config_manager = _create_config_manager_from_args(args, logger)

        # Get the requested value
        value = config_manager.get(args.key if args.key else None)

        # Format and print the value
        _print_formatted(value, args.format)
        return 0
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        return 1


def handle_set_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'set' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.set", level="INFO")
    try:
        # Create config manager with potential remote connection
        config_manager = _create_config_manager_from_args(args, logger)

        # Parse the value
        parsed_value = parse_value(args.value)

        # Set the value
        config_manager.set(args.key, parsed_value)

        # Validate and save
        if _validate_and_save(config_manager, getattr(args, "schema", None), logger):
            logger.info(f"Set {args.key} = {parsed_value}")
            return 0
        return 1
    except Exception as e:
        logger.error(f"Error setting configuration: {e}")
        return 1


def handle_delete_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'delete' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.delete", level="INFO")
    try:
        # Create config manager with potential remote connection
        config_manager = _create_config_manager_from_args(args, logger)

        # Delete the key
        if config_manager.delete(args.key):
            # Validate and save
            if _validate_and_save(config_manager, getattr(args, "schema", None), logger):
                logger.info(f"Deleted {args.key}")
                return 0
            return 1
        else:
            logger.warning(f"Key '{args.key}' not found")
            return 0
    except Exception as e:
        logger.error(f"Error deleting configuration: {e}")
        return 1


def handle_import_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'import' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.import", level="INFO")
    try:
        import_path = Path(args.import_file)

        if not import_path.exists():
            logger.error(f"Import file not found: {import_path}")
            return 1

        # Create config manager with potential remote connection
        config_manager = _create_config_manager_from_args(args, logger)

        # Load import data
        try:
            import_data = load_file(import_path, logger=logger)
        except Exception as e:
            logger.error(f"Error loading import file: {e}")
            return 1

        # Update configuration
        config_manager.update(import_data)

        # Validate and save
        if _validate_and_save(config_manager, getattr(args, "schema", None), logger):
            logger.info(f"Imported configuration from {import_path}")
            return 0
        return 1
    except Exception as e:
        logger.error(f"Error importing configuration: {e}")
        return 1


def handle_validate_command(
    args: argparse.Namespace, logger: Optional[logging.Logger] = None
) -> int:
    """Handle the 'validate' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.validate", level="INFO")
    try:

        if not HAS_SCHEMA_DEPS:
            logger.error(
                "Schema validation requires additional dependencies. "
                "Install them with: pip install nekoconf[schema]"
            )
            return 1

        # Create config manager with potential remote connection
        config_manager = _create_config_manager_from_args(args, logger)

        # Validate
        errors = config_manager.validate()
        if errors:
            logger.error("Validation failed:")
            for error in errors:
                logger.error(f"  - {error}")
            return 1
        else:
            logger.info("Validation successful")
            return 0
    except ImportError as e:
        logger.error(f"{e}")
        logger.error("Install dependencies with: pip install nekoconf[schema]")
        return 1
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        return 1


def handle_init_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'init' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.init", level="INFO")
    try:
        config_path = Path(args.config)

        # Check if file already exists
        if config_path.exists():
            logger.error(f"Configuration file already exists: {config_path}")
            return 1

        # Use template if provided
        if args.template:
            template_path = Path(args.template)
            if not template_path.exists():
                logger.error(f"Template file not found: {template_path}")
                return 1

            try:
                # Load template and save as new config
                template_data = load_file(template_path, logger=logger)
                save_file(config_path, template_data)
                logger.info(f"Created new configuration file from template: {config_path}")
            except Exception as e:
                logger.error(f"Error creating config from template: {e}")
                return 1
        else:
            # Create an empty configuration file
            save_file(config_path, {})
            logger.info(f"Created new empty configuration file: {config_path}")

        return 0
    except Exception as e:
        logger.error(f"Error creating empty config: {e}")
        return 1


def handle_connect_command(
    args: argparse.Namespace, logger: Optional[logging.Logger] = None
) -> int:
    """Handle the 'connect' command.

    Args:
        args: Command-line arguments
        logger: Optional logger instance

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.connect", level="INFO")

    try:
        # Check if remote dependencies are available
        try:

            if not HAS_REMOTE_DEPS:
                logger.error(
                    "Remote connection requires additional dependencies. "
                    "Install them with: pip install nekoconf[remote]"
                )
                return 1
        except ImportError:
            logger.error(
                "Remote connection requires additional dependencies. "
                "Install them with: pip install nekoconf[remote]"
            )
            return 1

        # Determine if we're using a local file or in-memory mode
        config_path = Path(args.config) if args.config else None
        in_memory = not args.config

        logger.info(f"Connecting to remote NekoConf server at {args.remote_url}")

        # Create the config manager with remote connection
        config_manager = NekoConfigManager(
            config_path=config_path,
            remote_url=args.remote_url,
            remote_api_key=args.api_key,
            remote_read_only=args.read_only,
            in_memory=in_memory,
            logger=logger,
        )

        # If we're not watching, just print the current config and exit
        if not args.watch:
            config_data = config_manager.get()
            _print_formatted(config_data, args.format)
            return 0

        # If watching, set up a handler to print updates
        import time

        logger.info("Watching for configuration changes (Ctrl+C to stop)...")

        # Initial configuration display
        config_data = config_manager.get()
        _print_formatted(config_data, args.format)

        # Set up change handler
        @config_manager.on_change("*")
        def on_config_change(path=None, old_value=None, new_value=None, event_type=None, **kwargs):
            print(f"\n--- Configuration changed at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            if path:
                print(f"Path: {path}")

                # Show what changed
                if old_value != new_value:
                    print("Old value:")
                    _print_formatted(old_value, args.format)

                    print("New value:")
                    _print_formatted(new_value, args.format)
            else:
                # Full config changed
                config_data = kwargs.get("config_data", {})
                print("New configuration:")
                _print_formatted(config_data, args.format)

        # Keep running until Ctrl+C
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Disconnecting from remote server")
            config_manager.cleanup()

        return 0

    except Exception as e:
        logger.error(f"Error connecting to remote server: {e}")
        import traceback

        logger.debug(traceback.format_exc())
        return 1


def main(args: Optional[List[str]] = None) -> int:
    """Run the NekoConf command-line interface.

    Args:
        args: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    if args is None:
        args = sys.argv[1:]

    logger: Optional[logging.Logger] = None

    # Debug mode handling
    if "--debug" in args:
        logger = getLogger("nekoconf.cli", level="DEBUG")
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Python version: {sys.version}")
        logger.debug(f"Script directory: {os.path.dirname(os.path.abspath(__file__))}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"System PATH: {os.environ.get('PATH', '').split(os.pathsep)}")
        args.remove("--debug")
    else:
        logger = getLogger("nekoconf.cli", level="INFO")

    parser = _create_parser()

    try:
        parsed_args = parser.parse_args(args)
    except Exception as e:
        logger.error(f"Error parsing arguments: {e}")
        if "--debug" in sys.argv:
            import traceback

            traceback.print_exc()
        return 1

    # Handle version request
    if getattr(parsed_args, "version", False):
        print(f"NekoConf version {__version__}")
        return 0

    # Show help if no command provided
    if not parsed_args.command:
        parser.print_help()
        return 1

    try:
        # Command handler mapping
        handlers = {
            "server": handle_server_command,
            "get": handle_get_command,
            "set": handle_set_command,
            "delete": handle_delete_command,
            "import": handle_import_command,
            "validate": handle_validate_command,
            "init": handle_init_command,
            "connect": handle_connect_command,
        }

        if parsed_args.command in handlers:
            return handlers[parsed_args.command](parsed_args, logger)
        else:
            logger.error(f"Unknown command: {parsed_args.command}")
            return 1

    except Exception as e:
        logger.error(f"Error: {e}")
        if "--debug" in sys.argv:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
