"""API module for NekoConf.

This module provides an API for other applications to consume configuration data
and receive updates when configurations change.
"""

import logging
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)

from nekoconf.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Type variable for type hints
T = TypeVar("T")


class ConfigAPI:
    """API for consuming configuration data from other applications.

    This class provides methods for external applications to access and observe
    configuration data managed by NekoConf.
    """

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
    ):
        """Initialize the configuration API.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
        """
        self.config_manager = ConfigManager(config_path, schema_path)
        self.config_manager.load()
        logger.debug(f"Initialized ConfigAPI with {config_path}")

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        return self.config_manager.get(key, default)

    @overload
    def get_typed(self, key: str, default: None = None) -> Any: ...

    @overload
    def get_typed(self, key: str, default: T) -> T: ...

    def get_typed(self, key: str, default: Optional[T] = None) -> Union[Any, T]:
        """Get a configuration value with type preservation.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value (preserving the type of default if provided)
        """
        value = self.get(key, default)
        if default is not None and value is not None:
            try:
                # Try to convert the value to the same type as default
                value_type = type(default)
                return value_type(value)
            except (ValueError, TypeError):
                logger.warning(
                    f"Failed to convert '{key}' to type {type(default).__name__}, using as-is"
                )
        return value

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get an integer configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The integer value or default if not found/not an integer
        """
        value = self.get(key, default)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Value for '{key}' is not a valid integer, using default")
            return default

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get a float configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The float value or default if not found/not a float
        """
        value = self.get(key, default)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Value for '{key}' is not a valid float, using default")
            return default

    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """Get a boolean configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The boolean value or default if not found/not a boolean
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        # Handle string values
        if isinstance(value, str):
            if value.lower() in ("true", "yes", "1", "on"):
                return True
            if value.lower() in ("false", "no", "0", "off"):
                return False

        # Handle numeric values
        try:
            return bool(int(value))
        except (ValueError, TypeError):
            logger.warning(f"Value for '{key}' is not a valid boolean, using default")
            return default

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a string configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The string value or default if not found
        """
        value = self.get(key, default)
        if value is None:
            return default
        return str(value)

    def get_list(self, key: str, default: Optional[List] = None) -> Optional[List]:
        """Get a list configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The list value or default if not found/not a list
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, list):
            return value

        logger.warning(f"Value for '{key}' is not a list, using default")
        return default

    def get_dict(self, key: str, default: Optional[Dict] = None) -> Optional[Dict]:
        """Get a dictionary configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The dictionary value or default if not found/not a dictionary
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, dict):
            return value

        logger.warning(f"Value for '{key}' is not a dictionary, using default")
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            value: The value to set
        """
        self.config_manager.set(key, value)

    def delete(self, key: str) -> bool:
        """Delete a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        result = self.config_manager.delete(key)
        if result:
            self.config_manager.save()
        return result

    def update(self, data: Dict[str, Any], deep_merge: bool = True) -> None:
        """Update multiple configuration values.

        Args:
            data: Dictionary of configuration values to update
            deep_merge: Whether to perform deep merge for nested dictionaries
        """
        self.config_manager.update(data, deep_merge)
        self.config_manager.save()

    def get_all(self) -> Dict[str, Any]:
        """Get the entire configuration.

        Returns:
            The complete configuration data
        """
        return self.config_manager.get()

    def observe(self, observer: Callable[[Dict[str, Any]], Any]) -> None:
        """Register an observer function to be called when configuration changes.

        The observer can be either a synchronous function or an async coroutine.

        Args:
            observer: Function or coroutine to call with updated configuration data
        """
        self.config_manager.register_observer(observer)

    def stop_observing(self, observer: Callable[[Dict[str, Any]], Any]) -> None:
        """Unregister an observer function.

        Args:
            observer: Function or coroutine to remove from observers
        """
        self.config_manager.unregister_observer(observer)

    def reload(self) -> Dict[str, Any]:
        """Reload configuration from file.

        Returns:
            The reloaded configuration data
        """
        return self.config_manager.load()

    def validate(self) -> List[str]:
        """Validate configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        return self.config_manager.validate()
