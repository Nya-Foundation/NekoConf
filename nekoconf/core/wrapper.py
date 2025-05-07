"""API module for NekoConf.

This module provides an API for other applications to consume configuration data
and receive updates when configurations change.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union, overload

from nekoconf.core.config import NekoConfigManager

from ..utils.helper import getLogger

# Type variable for type hints
T = TypeVar("T")


class NekoConfigWrapper:
    """A helper class for accessing and managing NekoConf configurations.

    This class provides methods for external applications to access and event handling
    configuration data managed by NekoConf.
    """

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
        logger: Optional[logging.Logger] = None,
        *,
        # Document the forwarded parameters
        env_override_enabled: bool = True,
        env_prefix="NEKOCONF",
        remote_url: Optional[str] = None,
        remote_api_key: Optional[str] = None,
        event_emission_enabled: bool = False,
        in_memory: bool = False,
        # Other important params you want to expose
        **kwargs: Any,
    ):
        """Initialize the configuration API.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
            logger: Logger instance for logging (optional)
            env_override_enabled: Enable environment variable overrides (default: True)
            env_prefix: Prefix for environment variables (default: "NEKOCONF")
            remote_url: URL for remote configuration (optional)
            remote_api_key: API key for remote configuration (optional)
            event_emission_enabled: Enable event emission for configuration changes (default: False)
            in_memory: Use in-memory storage for configuration (default: False)
        """
        self.logger = logger or getLogger(__name__)

        self.config = NekoConfigManager(
            config_path,
            schema_path,
            self.logger,
            env_override_enabled=env_override_enabled,
            env_prefix=env_prefix,
            remote_url=remote_url,
            remote_api_key=remote_api_key,
            event_emission_enabled=event_emission_enabled,
            in_memory=in_memory,
            **kwargs,
        )
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

    def __getattr__(self, name):
        """Delegate method calls to the underlying NekoConfigManager.

        This allows the NekoConfigClient to transparently access all methods
        of the underlying NekoConfigManager without having to explicitly
        define pass-through methods.

        Args:
            name: The name of the attribute/method to access

        Returns:
            The attribute or method from the underlying config manager

        Raises:
            AttributeError: If the attribute doesn't exist on the config manager
        """
        if hasattr(self.config, name):
            return getattr(self.config, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False
