"""Command-line interface for NekoConf."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

from nekoconf import HAS_REMOTE_DEPS, HAS_SCHEMA_DEPS, HAS_SERVER_DEPS
from nekoconf._version import __version__
from nekoconf.core.config import NekoConf
from nekoconf.server.app import NekoConfOrchestrator
from nekoconf.storage import RemoteStorageBackend
from nekoconf.utils.helper import getLogger, load_file, parse_value, save_file

LOGGER = getLogger("nekoconf.cli.main")


def str2bool(x):
    if x.lower() in ("yes", "true", "t", "1"):
        return True
    if x.lower() in ("no", "false", "f", "0"):
        return False
    raise argparse.ArgumentTypeError(f"Boolean value expected, got {x!r}")


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser."""
    parser = argparse.ArgumentParser(description="NekoConf - Simple configuration management")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--debug",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Enable debug logging",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server = subparsers.add_parser("server", help="Start configuration server")
    server.add_argument("--host", default="0.0.0.0", help="Server host")
    server.add_argument("--port", type=int, default=8000, help="Server port")
    server.add_argument("--config", "-c", help="Configuration file path")
    server.add_argument("--schema", help="Schema file path")
    server.add_argument("--api-key", help="API key for authentication")
    server.add_argument(
        "--event",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Event pipeline for configuration changes",
    )
    server.add_argument(
        "--read-only",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Read-only mode",
    )
    server.add_argument(
        "--reload",
        type=str2bool,
        nargs="?",
        const=True,
        default=False,
        help="Auto-reload for development",
    )

    # Connect command (connect to a remote server)
    connect = subparsers.add_parser("connect", help="Connect to a remote configuration server")
    connect.add_argument("--remote", help="Remote server URL")
    connect.add_argument("--app-name", help="Application name for remote server")
    connect.add_argument("--api-key", help="API key for remote server")
    connect.add_argument("--format", "-f", choices=["json", "yaml", "raw"], default="raw")

    # Get command
    get = subparsers.add_parser("get", help="Get configuration value")
    get.add_argument("key", nargs="?", help="Configuration key (optional)")
    get.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    get.add_argument("--format", "-f", choices=["json", "yaml", "raw"], default="raw")
    get.add_argument("--remote", help="Remote server URL")
    get.add_argument("--api-key", help="API key for remote server")

    # Set command
    set = subparsers.add_parser("set", help="Set configuration value")
    set.add_argument("key", help="Configuration key")
    set.add_argument("value", help="Configuration value")
    set.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    set.add_argument("--schema", help="Schema file for validation")
    set.add_argument("--remote", help="Remote server URL")
    set.add_argument("--api-key", help="API key for remote server")

    # Delete command
    delete = subparsers.add_parser("delete", help="Delete configuration value")
    delete.add_argument("key", help="Configuration key")
    delete.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    delete.add_argument("--schema", help="Schema file for validation")
    delete.add_argument("--remote", help="Remote server URL")
    delete.add_argument("--api-key", help="API key for remote server")

    # Validate command
    validate = subparsers.add_parser("validate", help="Validate configuration")
    validate.add_argument("--config", "-c", default="config.yaml", help="Configuration file")
    validate.add_argument("--schema", required=True, help="Schema file")
    validate.add_argument("--remote", help="Remote server URL")
    validate.add_argument("--api-key", help="API key for remote server")

    # Init command
    init = subparsers.add_parser("init", help="Initialize new configuration")
    init.add_argument("config", help="Configuration file to create")
    init.add_argument("--template", help="Template file to use")

    return parser


def create_config(
    config_path: Optional[str] = None,
    schema: Optional[str] = None,
    read_only: bool = False,
    remote_url: Optional[str] = None,
    remote_app_name: Optional[str] = None,
    api_key: Optional[str] = None,
    event: Optional[bool] = False,
) -> NekoConf:
    """Create a NekoConf instance from CLI arguments."""
    if remote_url:
        if not HAS_REMOTE_DEPS:
            raise ImportError("Remote features require: pip install nekoconf[remote]")
        from nekoconf.storage.remote import RemoteStorageBackend

        storage = RemoteStorageBackend(
            remote_url=remote_url, app_name=remote_app_name, api_key=api_key, logger=LOGGER
        )
    else:
        storage = config_path or "config.yaml"

    schema_path = Path(schema) if schema else None
    return NekoConf(
        storage=storage,
        schema_path=schema_path,
        read_only=read_only,
        event_emission_enabled=event,
        logger=LOGGER,
    )


def format_output(value: Any, format_type: str) -> str:
    """Format output according to specified format."""
    if format_type == "json":
        return json.dumps(value, indent=2)
    elif format_type == "yaml":

        return yaml.dump(value, default_flow_style=False)
    else:  # raw
        return str(value) if not isinstance(value, (dict, list)) else json.dumps(value, indent=2)


def cmd_server(args: argparse.Namespace) -> int:
    """Handle server command."""
    if not HAS_SERVER_DEPS:
        print("Server features require: pip install nekoconf[server]")
        return 1

    apps = {}
    if args.config:
        config = create_config(
            args.config,
            schema=args.schema,
            api_key=args.api_key,
            read_only=args.read_only,
            event=args.event,
        )
        apps["default"] = config

    orchestrator = NekoConfOrchestrator(
        apps=apps, api_key=args.api_key, read_only=args.read_only, logger=LOGGER
    )
    orchestrator.run(host=args.host, port=args.port, reload=args.reload)
    return 0


def cmd_connect(args: argparse.Namespace) -> int:
    """Connect to a remote configuration server."""

    if not HAS_REMOTE_DEPS:
        print("Remote connection requires: pip install nekoconf[remote]")
        return 1

    if not args.remote:
        print("Remote URL is required for connection")
        return 1

    config = create_config(
        remote_url=args.remote, remote_app_name=args.app_name, api_key=args.api_key
    )

    try:
        config_data = config.get_all()
        print(format_output(config_data, args.format or "json"))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_get(args: argparse.Namespace) -> int:
    """Handle get command."""
    try:
        config = create_config(args.config, remote_url=args.remote, api_key=args.api_key)
        if args.key:
            value = config.get(args.key)
        else:
            value = config.get_all()
        print(format_output(value, args.format))
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_set(args: argparse.Namespace) -> int:
    """Handle set command."""
    try:
        config = create_config(
            args.config, schema=args.schema, remote_url=args.remote, api_key=args.api_key
        )
        parsed_value = parse_value(args.value)
        config.set(args.key, parsed_value)

        if args.schema and not config.validate():
            print("Validation failed")
            return 1

        config.save()
        print(f"Set {args.key} = {parsed_value}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_delete(args: argparse.Namespace) -> int:
    """Handle delete command."""
    try:
        config = create_config(
            args.config, schema=args.schema, remote_url=args.remote, api_key=args.api_key
        )
        if config.delete(args.key):
            if args.schema and not config.validate():
                print("Validation failed")
                return 1
            config.save()
            print(f"Deleted {args.key}")
        else:
            print(f"Key '{args.key}' not found")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command."""
    if not HAS_SCHEMA_DEPS:
        print("Schema validation requires: pip install nekoconf[schema]")
        return 1

    try:
        config = create_config(
            args.config, schema=args.schema, remote_url=args.remote, api_key=args.api_key
        )
        errors = config.validate()
        if errors:
            print("Validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("Validation successful")
            return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_init(args: argparse.Namespace) -> int:
    """Handle init command."""
    try:
        config_path = Path(args.config)

        if config_path.exists():
            print(f"Configuration file already exists: {config_path}")
            return 1

        if args.template:
            template_path = Path(args.template)
            if not template_path.exists():
                print(f"Template file not found: {template_path}")
                return 1
            data = load_file(template_path)
        else:
            data = {}

        save_file(config_path, data)
        print(f"Created configuration file: {config_path}")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


def main_cli() -> int:
    """Main CLI entry point."""
    parser = create_parser()

    # Handle --debug flag
    if "--debug" in sys.argv:
        logging.basicConfig(level=logging.DEBUG)
        sys.argv.remove("--debug")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Command dispatch
    commands = {
        "server": cmd_server,
        "connect": cmd_connect,
        "get": cmd_get,
        "set": cmd_set,
        "delete": cmd_delete,
        "validate": cmd_validate,
        "init": cmd_init,
    }

    if args.command in commands:
        return commands[args.command](args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main_cli())
