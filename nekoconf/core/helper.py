"""API module for NekoConf.

This module provides an API for other applications to consume configuration data
and receive updates when configurations change.
"""

import logging
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    overload,
)

from nekoconf.core.config import NekoConfigManager

from .utils import getLogger

# Type variable for type hints
T = TypeVar("T")


class NekoConfigClient:
    """A helper class for accessing and managing NekoConf configurations.

    This class provides methods for external applications to access and event handling
    configuration data managed by NekoConf.
    """

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
        **kwargs: Any,
    ):
        """Initialize the configuration API.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
        """
        self.logger = logger or getLogger(__name__)

        self.config = NekoConfigManager(config_path, schema_path, self.logger, **kwargs)
        self.config.load()

        self.logger.debug(f"Initialized NekoConfigClient with {config_path}")

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        return self.config.get(key, default)

    @overload
    def get_typed(self, key: str, default: None = None) -> Any: ...

    @overload
    def get_typed(self, key: str, default: T) -> T: ...

    def get_typed(self, key: str, default: Optional[T] = None) -> Union[Any, T]:
        """Get a configuration value with type preservation.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
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
                self.logger.warning(
                    f"Failed to convert '{key}' to type {type(default).__name__}, using as-is"
                )
        return value

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        """Get an integer configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
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
            self.logger.warning(f"Value for '{key}' is not a valid integer, using default")
            return default

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        """Get a float configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
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
            self.logger.warning(f"Value for '{key}' is not a valid float, using default")
            return default

    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        """Get a boolean configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
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
            self.logger.warning(f"Value for '{key}' is not a valid boolean, using default")
            return default

    def get_str(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a string configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
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
            key: The configuration key (JMESPath expressions for nested values)
            default: Default value to return if key is not found

        Returns:
            The list value or default if not found/not a list
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, list):
            return value

        self.logger.warning(f"Value for '{key}' is not a list, using default")
        return default

    def get_dict(self, key: str, default: Optional[Dict] = None) -> Optional[Dict]:
        """Get a dictionary configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
            default: Default value to return if key is not found

        Returns:
            The dictionary value or default if not found/not a dictionary
        """
        value = self.get(key, default)
        if value is None:
            return default

        if isinstance(value, dict):
            return value

        self.logger.warning(f"Value for '{key}' is not a dictionary, using default")
        return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)
            value: The value to set
        """
        self.config.set(key, value)

    def delete(self, key: str) -> bool:
        """Delete a configuration value.

        Args:
            key: The configuration key (JMESPath expressions for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        result = self.config.delete(key)
        return result

    def update(self, data: Dict[str, Any], deep_merge: bool = True) -> None:
        """Update multiple configuration values.

        Args:
            data: Dictionary of configuration values to update
            deep_merge: Whether to perform deep merge for nested dictionaries
        """
        self.config.update(data, deep_merge)

    def save(self) -> bool:
        """Save the current configuration to file.

        Returns:
            True if save was successful, False otherwise
        """
        return self.config.save()

    def get_all(self) -> Dict[str, Any]:
        """Get the entire configuration.

        Returns:
            The complete configuration data
        """
        return self.config.get()

    def reload(self) -> Dict[str, Any]:
        """Reload configuration from file.

        Returns:
            The reloaded configuration data
        """
        return self.config.load()

    def validate(self) -> List[str]:
        """Validate configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        return self.config.validate()

    def on_change(self, path_pattern: str, priority: int = 100):
        """Register a handler for changes to a specific configuration path.

        This method provides a decorator that can be used to register a function
        as a handler for configuration changes at a specific path.

        Args:
            path_pattern: Path pattern to filter events (e.g., "database.connection")
            priority: Handler priority (lower number = higher priority)

        Returns:
            Decorator function

        Example:
            @config.on_change("database.connection")
            def handle_db_connection_change(old_value, new_value, **kwargs):
                # Reconnect to database with new settings
                pass
        """
        return self.config.on_change(path_pattern, priority)

    def on_event(self, event_type, path_pattern=None, priority=100):
        """Register a handler for specific event types.

        This method provides a decorator that can be used to register a function
        as a handler for specific types of configuration events.

        Args:
            event_type: Type of event to handle (or list of types)
            path_pattern: Optional path pattern to filter events
            priority: Handler priority (lower number = higher priority)

        Returns:
            Decorator function

        Example:
            @config.on_event(EventType.DELETE, "cache.*")
            def handle_cache_delete(path, old_value, **kwargs):
                # Clear cache entries when deleted
                pass

            @config.on_event([EventType.CREATE, EventType.UPDATE], "logging.*")
            def handle_logging_change(event_type, path, new_value, **kwargs):
                # Update logging configuration
                if event_type == EventType.CREATE:
                    # Initialize new logger
                    pass
                else:
                    # Update existing logger
                    pass
        """
        return self.config.on_event(event_type, path_pattern, priority)
