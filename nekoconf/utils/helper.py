"""Utility functions for NekoConf.

This module provides common utility functions used across the NekoConf package.
"""

import copy
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import colorlog
import jmespath
import jmespath.exceptions
import yaml

try:
    import tomli  # Python < 3.11
except ImportError:
    try:
        import tomllib as tomli  # Python >= 3.11
    except ImportError:
        tomli = None  # TOML support will be disabled


__all__ = [
    "getLogger",
    "create_file_if_not_exists",
    "save_file",
    "load_file",
    "parse_value",
    "deep_merge",
    "get_nested_value",
    "set_nested_value",
    "is_async_callable",
]


def getLogger(
    name: str,
    level: Union[int, str] = logging.INFO,
    format_str: str = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers: List[logging.Handler] = None,
) -> logging.Logger:
    """Create and configure a logger with sensible defaults and colored output.

    This function creates a new logger or retrieves an existing one with the
    given name, then configures it with the specified log level and format.

    Args:
        name: The name of the logger, typically the module name
        level: Logging level (either logging constant or string name)
        format_str: Message format string for the logger
        handlers: Optional list of handlers to add to the logger

    Returns:
        Configured logger instance
    """
    # Convert string level to int if necessary
    if isinstance(level, str):
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {level}")
        level = numeric_level

    # Get or create logger
    logger = logging.getLogger(name)

    # Only configure if it's a new logger (no handlers set up)
    if not logger.handlers:
        logger.setLevel(level)

        # Create default handler if none provided
        if not handlers:
            handler = colorlog.StreamHandler()
            handler.setLevel(level)

            # Define color scheme for different log levels
            color_formatter = colorlog.ColoredFormatter(
                format_str,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red,bg_white",
                },
            )
            handler.setFormatter(color_formatter)
            handlers = [handler]

        # Add all handlers to the logger
        for handler in handlers:
            logger.addHandler(handler)

        # Prevent propagation to the root logger to avoid duplicate logs
        logger.propagate = False

    return logger


def create_file_if_not_exists(file_path: Union[str, Path]) -> None:
    """Create a file if it does not exist.

    Args:
        file_path: Path to the file to create
    """
    file_path = Path(file_path)
    if file_path.exists():
        return

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)  # Create parent dirs
        file_path.touch()  # Create the file
    except Exception as e:
        raise IOError(f"Failed to create file: {e}") from e


def save_file(path: Union[str, Path], data: Any, logger: Optional[logging.Logger] = None) -> bool:
    """Save data to a YAML, JSON, or TOML file based on file extension.

    Args:
        path: Path to the file
        data: Data to save

    Returns:
        True if successful, False otherwise
    """
    path = Path(path)
    logger = logger or getLogger(__name__)
    try:
        # Create parent directory if it doesn't exist
        path.parent.mkdir(parents=True, exist_ok=True)

        # Determine file format
        if path.suffix.lower() == ".yaml" or path.suffix.lower() == ".yml":
            # Save as YAML
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        elif path.suffix.lower() == ".json":
            # Save as JSON
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        elif path.suffix.lower() == ".toml":
            # Save as TOML
            try:
                import tomli_w

                with open(path, "wb") as f:
                    tomli_w.dump(data, f)
            except ImportError:
                logger.error(
                    "TOML format requested but tomli_w package not available. "
                    "Install with: pip install tomli_w"
                )
                return False
        else:
            # Default to YAML for unknown extensions
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)

        return True
    except Exception as e:
        logger.error(f"Error saving file {path}: {e}")
        return False


def load_file(path: Union[str, Path], logger: Optional[logging.Logger] = None) -> Any:
    """Load data from a YAML, JSON, or TOML file based on file extension.

    Args:
        path: Path to the file
        logger: Optional logger to use for warnings/errors

    Returns:
        Loaded data, or empty dict if loading failed or file not found
    """
    logger = logger or getLogger(__name__)
    path = Path(path)

    if not path.exists():
        logger.warning(f"File not found: {path}")
        return {}  # Return empty dict instead of None

    try:
        # Determine file format
        if path.suffix.lower() == ".yaml" or path.suffix.lower() == ".yml":
            # Load YAML
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        elif path.suffix.lower() == ".json":
            # Load JSON
            with open(path, "r") as f:
                return json.load(f)
        elif path.suffix.lower() == ".toml":
            # Load TOML
            try:
                # Try tomllib in Python 3.11+
                try:
                    import tomllib

                    with open(path, "rb") as f:
                        return tomllib.load(f) or {}
                except ImportError:
                    # Fall back to tomli
                    try:
                        import tomli

                        with open(path, "rb") as f:
                            return tomli.load(f) or {}
                    except ImportError:
                        logger.error(
                            "TOML format requested but neither tomllib (Python 3.11+) "
                            "nor tomli package is available. "
                            "Install with: pip install tomli"
                        )
                        return {}  # Return empty dict instead of None
            except Exception as e:
                logger.error(f"Error parsing TOML file {path}: {e}")
                return {}  # Return empty dict instead of None
        else:
            # Default to YAML for unknown extensions
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error loading file {path}: {e}")
        return {}  # Return empty dict instead of None


def parse_value(value_str: str) -> Any:
    """Parse a string value into the appropriate Python type.

    Args:
        value_str: String value to parse

    Returns:
        Parsed value as the appropriate type
    """
    # Handle empty string
    if not value_str:
        return ""

    # Try to parse as JSON
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        pass

    # Handle common literal values
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    if value_str.lower() == "null" or value_str.lower() == "none":
        return None

    # Try to parse as number
    try:
        if "." in value_str:
            return float(value_str)
        else:
            return int(value_str)
    except ValueError:
        pass

    # Default to returning as string
    return value_str


def deep_merge(
    source: Dict[str, Any], destination: Dict[str, Any], in_place: bool = False
) -> Dict[str, Any]:
    """Recursively merge two dictionaries.

    Args:
        source: Source dictionary to merge from
        destination: Destination dictionary to merge into
        in_place: If True, modify destination in place; otherwise, return a new dict

    Returns:
        Merged dictionary
    """
    if not isinstance(destination, dict) or not isinstance(source, dict):
        return source

    if in_place:
        result = destination
    else:
        result = copy.deepcopy(destination)

    for key, value in source.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(value, result[key], in_place)
        else:
            result[key] = value
    return result


def get_nested_value(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from a nested dictionary using JMESPath expressions or JMESPath expressions.

    Args:
        data: Dictionary to get value from
        key: Key in JMESPath format (e.g., "server.host" or "servers[*].host")
        default: Default value to return if key is not found

    Returns:
        Value from the dictionary or default if not found
    """
    if not key:
        return data

    try:
        result = jmespath.search(key, data)
        if result is not None:  # JMESPath returns None for non-matches
            return result
    except jmespath.exceptions.JMESPathTypeError:
        return default

    return default


def set_nested_value(data: Dict[str, Any], key: str, value: Any) -> bool:
    """Set a value in a nested dictionary using JMESPath expressions.

    Args:
        data: Dictionary to set value in
        key: Key in JMESPath expressions (e.g., "server.host")
        value: Value to set

    Returns:
        True if value was changed, False otherwise
    """
    if not key:
        return False

    parts = key.split(".") if "." in key else [key]
    current = data

    # Navigate to the parent of the target key
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    # Check if value actually changes
    last_key = parts[-1]
    if last_key in current and current[last_key] == value:
        return False

    # Set the value
    current[last_key] = value
    return True


def is_async_callable(func):
    # Check if it's directly a coroutine function
    if inspect.iscoroutinefunction(func):
        return True

    # Check if it's a callable with an async __call__ method
    if hasattr(func, "__call__") and inspect.iscoroutinefunction(func.__call__):
        return True

    # Check for other awaitable objects
    if hasattr(func, "__await__"):
        return True

    return False
