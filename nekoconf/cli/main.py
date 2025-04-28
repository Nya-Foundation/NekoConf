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
from typing import List, Optional

import yaml

from nekoconf._version import __version__
from nekoconf.core.config import NekoConfigManager
from nekoconf.core.utils import getLogger, load_file, parse_value, save_file
from nekoconf.server.app import NekoConfigServer


def _create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        The configured argument parser
    """
    parser = argparse.ArgumentParser(description="NekoConf - Configuration management with web UI")
    parser.add_argument("--version", action="store_true", help="Show version information and exit")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the configuration web server")
    server_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    server_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to run the server on (default: 127.0.0.1)",
    )
    server_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)",
    )

    server_parser.add_argument(
        "--schema",
        type=str,
        help="Path to a schema file for validation (optional)",
    )
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
    get_parser = subparsers.add_parser("get", help="Get a configuration value")
    get_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    get_parser.add_argument(
        "key",
        type=str,
        nargs="?",
        help="Configuration key to retrieve (if omitted, returns all)",
    )
    get_parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "yaml", "raw"],
        default="raw",
        help="Output format (default: raw)",
    )

    # Set command
    set_parser = subparsers.add_parser("set", help="Set a configuration value")
    set_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    set_parser.add_argument("key", type=str, help="Configuration key to set")
    set_parser.add_argument("value", type=str, help="Value to set for the key")
    set_parser.add_argument(
        "--schema",
        type=str,
        help="Path to a schema file for validation (optional)",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a configuration value")
    delete_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    delete_parser.add_argument("key", type=str, help="Configuration key to delete")
    delete_parser.add_argument(
        "--schema",
        type=str,
        help="Path to a schema file for validation (optional)",
    )

    # Import command
    import_parser = subparsers.add_parser("import", help="Import configuration from a file")
    import_parser.add_argument(
        "--config",
        "-c",
        type=str,
        required=True,
        help="Path to the target configuration file (YAML or JSON)",
    )
    import_parser.add_argument(
        "import_file",
        type=str,
        help="File to import (YAML or JSON)",
    )
    import_parser.add_argument(
        "--deep-merge",
        action="store_true",
        default=True,
        help="Perform deep merge of nested objects (default: True)",
    )
    import_parser.add_argument(
        "--schema",
        type=str,
        help="Path to a schema file for validation (optional)",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate configuration against a schema"
    )
    validate_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    validate_parser.add_argument(
        "--schema",
        "-s",
        type=str,
        required=True,
        help="Path to the schema file (YAML or JSON)",
    )

    # Create empty config command
    init_parser = subparsers.add_parser("init", help="Create a new empty configuration file")
    init_parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the new configuration file (YAML or JSON)",
        default="config.yaml",  # Default value for testing purposes
    )
    init_parser.add_argument(
        "--template",
        "-t",
        type=str,
        help="Template file to use (optional)",
    )

    return parser


def handle_server_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'server' command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """

    logger = logger or getLogger("nekoconf.cli.server", level="INFO")

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


def handle_get_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'get' command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """

    logger = logger or getLogger("nekoconf.cli.get", level="INFO")

    try:
        config_path = Path(args.config)

        # Load configuration
        config_manager = NekoConfigManager(config_path)
        config_manager.load()

        # Get the requested value
        value = config_manager.get(args.key if args.key else None)

        # Format and print the value
        if args.format == "json":
            print(json.dumps(value, indent=2))
        elif args.format == "yaml":
            print(yaml.dump(value, default_flow_style=False))
        else:  # raw format
            if args.key is None or isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2))
            else:
                print(value)

        return 0
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        return 1


def handle_set_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'set' command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """

    logger = logger or getLogger("nekoconf.cli.set", level="INFO")
    try:
        config_path = Path(args.config)
        schema_path = Path(args.schema) if args.schema else None

        # Create config manager
        config_manager = NekoConfigManager(config_path, schema_path)
        config_manager.load()

        # Parse the value
        parsed_value = parse_value(args.value)

        # Set the value
        config_manager.set(args.key, parsed_value)

        # Validate if a schema is provided
        if schema_path:
            errors = config_manager.validate()
            if errors:
                logger.error("Validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                return 1

        # Save the configuration
        if config_manager.save():
            logger.info(f"Set {args.key} = {parsed_value}")
            return 0
        else:
            return 1
    except Exception as e:
        logger.error(f"Error setting configuration: {e}")
        return 1


def handle_delete_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'delete' command.

    Args:
        args: Command-line arguments

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.delete", level="INFO")
    try:
        config_path = Path(args.config)
        schema_path = Path(args.schema) if args.schema else None

        # Create config manager
        config_manager = NekoConfigManager(config_path, schema_path)
        config_manager.load()

        # Delete the key
        if config_manager.delete(args.key):
            # Validate if a schema is provided
            if schema_path:
                errors = config_manager.validate()
                if errors:
                    logger.error("Validation failed:")
                    for error in errors:
                        logger.error(f"  - {error}")
                    return 1

            # Save the configuration
            if config_manager.save():
                logger.info(f"Deleted {args.key}")
                return 0
            else:
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

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.import", level="INFO")
    try:
        config_path = Path(args.config)
        import_path = Path(args.import_file)
        schema_path = Path(args.schema) if args.schema else None

        if not import_path.exists():
            logger.error(f"Import file not found: {import_path}")
            return 1

        # Create config manager
        config_manager = NekoConfigManager(config_path, schema_path)
        config_manager.load()

        # Load import data
        try:
            import_data = load_file(import_path)
        except Exception as e:
            logger.error(f"Error loading import file: {e}")
            return 1

        # Update configuration
        config_manager.update(import_data, args.deep_merge)

        # Validate if a schema is provided
        if schema_path:
            errors = config_manager.validate()
            if errors:
                logger.error("Validation failed:")
                for error in errors:
                    logger.error(f"  - {error}")
                return 1

        # Save the configuration
        if config_manager.save():
            logger.info(f"Imported configuration from {import_path} to {config_path}")
            return 0
        else:
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

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    logger = logger or getLogger("nekoconf.cli.validate", level="INFO")
    try:
        config_path = Path(args.config)
        schema_path = Path(args.schema)

        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return 1

        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return 1

        # Create config manager
        config_manager = NekoConfigManager(config_path, schema_path)
        config_manager.load()

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
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        return 1


def handle_init_command(args: argparse.Namespace, logger: Optional[logging.Logger] = None) -> int:
    """Handle the 'init' command.

    Args:
        args: Command-line arguments

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
                template_data = load_file(template_path)
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
