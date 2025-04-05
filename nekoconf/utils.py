"""Utility functions for NekoConf.

This module provides common utility functions used across the NekoConf package.
"""

import asyncio
import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union, Callable, List, TypeVar

import yaml

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Define type variable for generic functions


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
        logger.info(f"Created file: {file_path}")
    except Exception as e:
        logger.error(f"Failed to create file {file_path}: {e}")
        raise IOError(f"Failed to create file: {e}") from e


def load_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from a YAML or JSON file.

    Args:
        file_path: Path to the file to load

    Returns:
        Dictionary containing the loaded configuration

    Raises:
        ValueError: If the file has an invalid format
        IOError: If the file cannot be read
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.warning(f"File does not exist: {file_path}")
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Empty file case
        if not content.strip():
            return {}

        # Determine file type by extension
        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            data = yaml.safe_load(content)
        elif suffix == ".json":
            data = json.loads(content)
        else:
            # Try YAML first, then JSON
            try:
                data = yaml.safe_load(content)
            except yaml.YAMLError:
                data = json.loads(content)

        return {} if data is None else data
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid file format: {e}") from e
    except Exception as e:
        raise IOError(f"Failed to load file: {e}") from e


def save_file(file_path: Union[str, Path], data: Dict[str, Any]) -> None:
    """Save configuration to a YAML or JSON file.

    Args:
        file_path: Path to the file to save
        data: Configuration data to save

    Raises:
        IOError: If the file cannot be written
    """
    file_path = Path(file_path)

    # Create directory if it doesn't exist
    os.makedirs(file_path.parent, exist_ok=True)

    try:
        # Determine file type by extension
        suffix = file_path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        else:  # Default to JSON
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        raise IOError(f"Failed to save file: {e}") from e


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


def deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries.

    Args:
        source: Source dictionary to merge from
        destination: Destination dictionary to merge into

    Returns:
        Merged dictionary
    """
    if not isinstance(destination, dict) or not isinstance(source, dict):
        return source

    result = destination.copy()
    for key, value in source.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(value, result[key])

            # Log the merge operation for debugging
            print(f"Merged key '{key}': {result[key]} with {value}")
        else:
            result[key] = value
    return result


def get_nested_value(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get a value from a nested dictionary using dot notation.

    Args:
        data: Dictionary to get value from
        key: Key in dot notation (e.g., "server.host")
        default: Default value to return if key is not found

    Returns:
        Value from the dictionary or default if not found
    """
    if not key:
        return data

    parts = key.split(".")
    current = data

    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]

    return current


def set_nested_value(data: Dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a nested dictionary using dot notation.

    Args:
        data: Dictionary to set value in
        key: Key in dot notation (e.g., "server.host")
        value: Value to set
    """
    if not key:
        return

    parts = key.split(".") if "." in key else [key]
    current = data

    # Navigate to the parent of the target key
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    # Set the value
    current[parts[-1]] = value


async def notify_observers(
    observers: List[Callable[[Dict[str, Any]], Any]],
    config_data: Dict[str, Any],
) -> None:
    """Notify observers of configuration changes.

    Args:
        observers: List of observer functions to call
        config_data: Configuration data to pass to observers
    """
    for observer in observers:
        try:
            # Check if the observer is an async function or has async __call__
            if is_async_callable(observer):
                await observer(config_data)
            else:
                observer(config_data)
        except Exception as e:
            logger.error(f"Error in observer {observer.__name__}: {e}")


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
