"""Configuration manager module for NekoConf.

This module provides functionality to read, write, and manage configuration files
in YAML and JSON formats.
"""

import asyncio
import inspect
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, Set

from nekoconf.utils import (
    load_file,
    save_file,
    deep_merge,
    get_nested_value,
    set_nested_value,
    notify_observers,
    create_file_if_not_exists,
    is_async_callable,
)

logger = logging.getLogger(__name__)


class ConfigManager:
    """Configuration manager for reading, writing, and observing configuration files."""

    def __init__(
        self,
        config_path: Union[str, Path],
        schema_path: Optional[Union[str, Path]] = None,
    ) -> None:
        """Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
            schema_path: Path to the schema file for validation (optional)
        """
        self.config_path = Path(config_path)
        self.schema_path = Path(schema_path) if schema_path else None
        self.config_data: Dict[str, Any] = {}
        self.observers: Set[Callable] = set()
        self._load_validators()
        self._init_config()  # Load the initial configuration

    def _init_config(self) -> None:
        """Initialize the configuration by loading it from the file."""
        create_file_if_not_exists(self.config_path)
        self.load()

    def _load_validators(self) -> None:
        """Load schema validators if available."""
        self.validator = None
        if self.schema_path:
            try:
                from nekoconf.schema_validator import SchemaValidator

                self.validator = SchemaValidator(self.schema_path)
                logger.debug(f"Loaded schema validator from {self.schema_path}")
            except ImportError:
                logger.warning(
                    "Schema validation requested but schema_validator module not available. "
                    "Install with pip install nekoconf[schema]"
                )
            except Exception as e:
                logger.error(f"Failed to load schema validator: {e}")

    def load(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns:
            The loaded configuration data
        """
        try:
            if self.config_path.exists():
                self.config_data = load_file(self.config_path)
                logger.debug(f"Loaded configuration from {self.config_path}")
            else:
                logger.warning(f"Configuration file not found: {self.config_path}")
                self.config_data = {}
            return self.config_data
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config_data = {}
            return self.config_data

    def save(self) -> bool:
        """Save configuration to file.

        Returns:
            True if successful, False otherwise
        """
        try:
            save_file(self.config_path, self.config_data)
            logger.debug(f"Saved configuration to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration data.

        Returns:
            The entire configuration data as a dictionary
        """
        return self.config_data

    def get(self, key: Optional[str] = None, default: Any = None) -> Any:
        """Get a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            default: Default value to return if key is not found

        Returns:
            The configuration value or default if not found
        """
        if key is None:
            return self.config_data

        return get_nested_value(self.config_data, key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)
            value: The value to set
        """
        set_nested_value(self.config_data, key, value)

        self._notify_observers()

    def delete(self, key: str) -> bool:
        """Delete a configuration value.

        Args:
            key: The configuration key (dot notation for nested values)

        Returns:
            True if the key was deleted, False if it didn't exist
        """
        parts = key.split(".")
        data = self.config_data

        # Navigate to the parent of the target key
        for i, part in enumerate(parts[:-1]):
            if part not in data or not isinstance(data[part], dict):
                return False
            data = data[part]

        # Delete the key if it exists
        if parts[-1] in data:
            del data[parts[-1]]
            self._notify_observers()
            return True

        return False

    def update(self, data: Dict[str, Any], deep_merge_enabled: bool = True) -> None:
        """Update multiple configuration values.

        Args:
            data: Dictionary of configuration values to update
            deep_merge_enabled: Whether to perform deep merge for nested dictionaries
        """
        if deep_merge_enabled:
            self.config_data = deep_merge(source=data, destination=self.config_data)
        else:
            self.config_data.update(data)

        self.save()  # Save the configuration after setting the value
        self._notify_observers()

    def register_observer(self, observer: Callable) -> None:
        """Register an observer function to be called when configuration changes.

        Args:
            observer: Function to call with the updated configuration data
        """
        self.observers.add(observer)
        logger.debug(f"Registered configuration observer: {observer.__name__}")

    def unregister_observer(self, observer: Callable) -> None:
        """Unregister an observer function.

        Args:
            observer: Function to remove from observers
        """
        if observer in self.observers:
            self.observers.remove(observer)
            logger.debug(f"Unregistered configuration observer: {observer.__name__}")

    def _notify_observers(self) -> None:
        """Notify all observers of configuration changes."""
        if not self.observers:
            return

        # split the observers into async and sync list
        async_observers = [obs for obs in self.observers if is_async_callable(obs)]

        # observers that are not async functions
        sync_observers = [obs for obs in self.observers if not is_async_callable(obs)]

        # Notify synchronous observers
        for observer in sync_observers:
            try:
                observer(self.config_data)
            except Exception as e:
                logger.error(f"Error in observer {observer.__name__}: {e}")

        # Use asyncio to properly handle async observers
        if not async_observers:
            return

        try:
            loop = asyncio.get_event_loop()
            # Check if we're in an event loop
            if loop.is_running():
                asyncio.create_task(notify_observers(async_observers, self.config_data))
            else:
                # If not in an event loop, run the coroutine in a new event loop
                asyncio.run(notify_observers(async_observers, self.config_data))
        except Exception as e:
            logger.error(f"Error scheduling async observers: {e}")

    def validate(self) -> List[str]:
        """Validate configuration against schema.

        Returns:
            List of validation error messages (empty if valid)
        """
        if not self.validator:
            logger.warning("No schema validator available, skipping validation")
            return []

        return self.validator.validate(self.config_data)
