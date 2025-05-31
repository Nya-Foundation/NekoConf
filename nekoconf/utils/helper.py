"""Utility functions for NekoConf.

This module provides common utility functions used across the NekoConf package.
"""

import ast
import copy
import inspect
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import colorlog
except ImportError:
    colorlog = None

try:
    import yaml
except ImportError:
    yaml = None

try:
    import tomllib  # Python >= 3.11
except ImportError:
    try:
        import tomli as tomllib  # Python < 3.11
    except ImportError:
        tomllib = None  # TOML support will be disabled


__all__ = [
    "getLogger",
    "create_file_if_not_exists",
    "save_file",
    "load_file",
    "parse_value",
    "deep_merge",
    "get_nested_value",
    "set_nested_value",
    "delete_nested_value",
    "parse_path",
    "is_async_callable",
]


def getLogger(
    name: str,
    level: int = logging.INFO,
    format_str: str = "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers: List[logging.Handler] = None,
) -> logging.Logger:
    """Create and configure a logger with sensible defaults and colored output.

    This function creates a new logger or retrieves an existing one with the
    given name, then configures it with the specified log level and format.

    Args:
        name: The name of the logger, typically the module name
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
        format_str: Message format string for the logger
        handlers: Optional list of handlers to add to the logger

    Returns:
        Configured logger instance
    """
    # Environment variable overrides
    env_level = os.getenv("LOG_LEVEL", None)
    if env_level:
        numeric_level = getattr(logging, env_level.upper(), None)
        if isinstance(numeric_level, int):
            level = numeric_level
    # Get or create logger
    logger = logging.getLogger(name)

    # Only configure if it's a new logger (no handlers set up)
    if not logger.handlers:
        logger.setLevel(level)

        # Create default handler if none provided
        if not handlers:
            if colorlog:
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
            else:
                handler = logging.StreamHandler()
                handler.setLevel(level)
                formatter = logging.Formatter(format_str.replace("%(log_color)s", ""))
                handler.setFormatter(formatter)
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
                if yaml:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                else:
                    json.dump(data, f, indent=2)  # Fallback to JSON
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
                if yaml:
                    yaml.dump(data, f, default_flow_style=False)
                else:
                    json.dump(data, f, indent=2)  # Fallback to JSON

        return True
    except Exception as e:
        logger.error(f"Error saving file {path}: {e}")
        return False


def load_string(data: str, format: str = "json") -> Any:
    """Load data from a string based on the specified format.

    Args:
        data: String containing the data
        format: Format of the data (e.g., "json", "yaml", "toml")

    Returns:
        Loaded data as a dictionary, or empty dict if loading failed
    """
    if not data.strip():
        return {}

    if format == "yaml":
        return yaml.safe_load(data) or {}
    elif format == "toml":
        return tomllib.loads(data) or {}
    else:
        return json.loads(data)  # Fallback to JSON


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
                if yaml:
                    return yaml.safe_load(f) or {}
                else:
                    return json.load(f)  # Fallback to JSON
        elif path.suffix.lower() == ".json":
            # Load JSON
            with open(path, "r") as f:
                return json.load(f)
        elif path.suffix.lower() == ".toml":
            # Load TOML
            try:
                if tomllib:
                    with open(path, "rb") as f:
                        return tomllib.load(f) or {}
                else:
                    logger.error(
                        "TOML format requested but tomllib/tomli package not available. "
                        "Install with: pip install tomli"
                    )
                    return {}
            except Exception as e:
                logger.error(f"Error parsing TOML file {path}: {e}")
                return {}
        else:
            # Default to YAML for unknown extensions
            with open(path, "r") as f:
                if yaml:
                    return yaml.safe_load(f) or {}
                else:
                    return json.load(f)  # Fallback to JSON
    except Exception as e:
        logger.error(f"Error loading file {path}: {e}")
        return {}  # Return empty dict instead of None


def parse_value(value_str: str) -> Any:
    """Parse environment variable value with robust type detection.

    Uses ast.literal_eval for safety and falls back to string preservation.
    """
    if not value_str:
        return ""

    # Handle explicit boolean strings
    lower_val = value_str.lower()
    if lower_val in ("true", "yes", "1", "on"):
        return True
    elif lower_val in ("false", "no", "0", "off"):
        return False
    elif lower_val in ("null", "none", "~", ""):
        return None

    # Try ast.literal_eval for safe evaluation of Python literals
    try:
        # This safely handles: numbers, strings, lists, dicts, tuples, etc.
        return ast.literal_eval(value_str)
    except (ValueError, SyntaxError):
        pass

    # For JSON-like structures that ast can't handle
    if value_str.startswith(("{", "[")):
        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            pass

    # Preserve original string (including quotes)
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


def _parse_path_segment(segment: str) -> List[str]:
    """Parse a single path segment, handling array notation.

    Examples:
        "key" -> ["key"]
        "key[0]" -> ["key", "0"]
        "key[*]" -> ["key", "*"]
    """
    match = re.match(r"^([^[\]]+)\[([^\]]+)\]$", segment)
    if match:
        key, index = match.groups()
        return [key, index]
    return [segment]


def parse_path(path: str) -> List[str]:
    """Parse dot notation path into flat list of keys and indices.

    Examples:
        "database.host" -> ["database", "host"]
        "servers[0].host" -> ["servers", "0", "host"]
        "apps[*].config.*.port" -> ["apps", "*", "config", "*", "port"]
    """
    if not path:
        return []

    result = []
    for segment in path.split("."):
        result.extend(_parse_path_segment(segment))

    return result


def get_nested_value(data: Dict[str, Any], path: str, default: Any = None) -> Any:
    """Get a value from a nested dictionary using dot notation.

    Examples:
        get_nested_value(data, "database.host")
        get_nested_value(data, "servers[0].port")
    """
    if not path:
        return data

    try:
        current = data
        for key in parse_path(path):
            if key.isdigit():
                current = current[int(key)]
            else:
                current = current[key]
        return current
    except (KeyError, IndexError, TypeError):
        return default


def set_nested_value(data: Dict[str, Any], path: str, value: Any) -> bool:
    """Set a value in a nested dictionary using dot notation.

    Examples:
        set_nested_value(data, "database.host", "localhost")
        set_nested_value(data, "servers[0].port", 8080)
    """
    if not path:
        return False

    # Check if current value is the same to avoid unnecessary changes
    sentinel = object()
    if get_nested_value(data, path, sentinel) == value:
        return False

    keys = parse_path(path)
    if not keys:
        return False

    current = data

    # Navigate to the parent, creating structure as needed
    for key in keys[:-1]:
        if key.isdigit():
            # This is an array index (came from [index] notation)
            index = int(key)
            if not isinstance(current, list):
                return False
            # Extend list if necessary
            while len(current) <= index:
                current.append({})
            current = current[index]
        else:
            # This is a regular key - always create as dict
            if key not in current:
                current[key] = {}
            current = current[key]

    # Set the final value
    final_key = keys[-1]
    try:
        if final_key.isdigit() and isinstance(current, list):
            # Setting array element
            index = int(final_key)
            while len(current) <= index:
                current.append(None)
            current[index] = value
        else:
            # Setting dict key (even if key looks like number)
            current[final_key] = value
        return True
    except (KeyError, IndexError, TypeError):
        return False


def delete_nested_value(data: Dict[str, Any], path: str) -> tuple[bool, Any]:
    """Delete a value from a nested dictionary using dot notation.

    Returns:
        Tuple of (success, old_value)
    """
    if not path:
        return False, None

    # Check if key exists and get old value
    sentinel = object()
    old_value = get_nested_value(data, path, sentinel)
    if old_value is sentinel:
        return False, None

    keys = parse_path(path)
    if not keys:
        return False, None

    current = data

    # Navigate to the parent
    try:
        for key in keys[:-1]:
            if key.isdigit():
                current = current[int(key)]
            else:
                current = current[key]
    except (KeyError, IndexError, TypeError):
        return False, None

    # Delete the final key/index
    final_key = keys[-1]
    try:
        if final_key.isdigit():
            index = int(final_key)
            if not isinstance(current, list):
                return False, None
            del current[index]
        else:
            del current[final_key]
        return True, old_value
    except (KeyError, IndexError, TypeError):
        return False, None


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
