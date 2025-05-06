"""CLI parameter definitions for NekoConf.

This module defines reusable parameter sets for the NekoConf CLI to reduce code duplication.
"""

from argparse import ArgumentParser
from typing import Callable


def add_config_param(parser: ArgumentParser) -> None:
    """Add the standard config file parameter to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        help="Path to the configuration file (YAML, JSON, or TOML)",
        default="config.yaml",
    )


def add_schema_param(parser: ArgumentParser) -> None:
    """Add the schema parameter to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--schema",
        type=str,
        help="Path to a schema file for validation (optional)",
    )


def add_format_param(parser: ArgumentParser) -> None:
    """Add the output format parameter to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "yaml", "raw"],
        default="raw",
        help="Output format (default: raw)",
    )


def add_remote_params(parser: ArgumentParser) -> None:
    """Add remote configuration parameters to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--remote-url",
        type=str,
        help="URL of a remote NekoConf server to connect to (e.g., 'http://config-server:8000')",
    )
    parser.add_argument(
        "--remote-api-key",
        type=str,
        help="API key for authentication with the remote server",
    )


def add_read_only_param(parser: ArgumentParser) -> None:
    """Add the read-only parameter to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--remote-read-only",
        action="store_true",
        help="Use read-only mode with the remote server (prevents writing changes back)",
    )


def add_in_memory_param(parser: ArgumentParser) -> None:
    """Add the in-memory parameter to a parser.

    Args:
        parser: The ArgumentParser to add parameters to
    """
    parser.add_argument(
        "--in-memory",
        action="store_true",
        help="Use in-memory mode without file persistence",
    )


def add_command(
    subparsers,
    name: str,
    help_text: str,
    add_config: bool = True,
    add_params_fn: Callable = None,
) -> ArgumentParser:
    """Add a command to the subparsers with standard options.

    Args:
        subparsers: The subparsers object to add the command to
        name: Command name
        help_text: Help text for the command
        add_params_fn: Optional function to add additional parameters

    Returns:
        The created parser for the command
    """
    parser = subparsers.add_parser(name, help=help_text)

    if add_config:
        # Add common parameters
        add_config_param(parser)

    parser.add_argument(
        "--event",
        "-e",
        type=bool,
        help="Enable Change Events (CHANGE, CREATE, DELETE, UPDATE...) Notification (default: False)",
        default=False,
    )

    # Add additional parameters if specified
    if add_params_fn:
        add_params_fn(parser)

    return parser
