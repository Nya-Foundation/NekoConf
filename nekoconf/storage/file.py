"""File-based storage backend."""

from pathlib import Path
from typing import Any, Dict, Union

from ..utils.helper import create_file_if_not_exists, load_file, save_file
from .base import StorageBackend, StorageError


class FileStorageBackend(StorageBackend):
    """Storage backend that persists configuration to a file.

    Supports YAML, JSON, and TOML file formats.
    """

    def __init__(self, config_path: Union[str, Path], **kwargs):
        """Initialize the file storage backend.

        Args:
            config_path: Path to the configuration file
            **kwargs: Additional arguments passed to parent class
        """
        super().__init__(**kwargs)
        self.config_path = Path(config_path)

        # Create file if it doesn't exist
        create_file_if_not_exists(self.config_path)

    def __str__(self):
        return f"{self.__class__.__name__}(config_path={self.config_path})"

    def load(self) -> Dict[str, Any]:
        """Load configuration data from file.

        Returns:
            Dictionary containing the configuration data

        Raises:
            StorageError: If file loading fails
        """
        try:
            if self.config_path.exists():
                data = load_file(self.config_path) or {}
                self.logger.debug(f"Loaded configuration from file: {self.config_path}")
                return data
            else:
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                return {}

        except Exception as e:
            error_msg = f"Error loading configuration file {self.config_path}: {e}"
            self.logger.error(error_msg)
            raise StorageError(error_msg) from e

    def save(self, data: Dict[str, Any]) -> bool:
        """Save configuration data to file.

        Args:
            data: Configuration data to save

        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Check if data has actually changed to avoid unnecessary writes
            existing_data = load_file(self.config_path) or {}
            if existing_data == data:
                self.logger.debug("No changes detected, not saving configuration")
                return True

            save_file(self.config_path, data)
            self.logger.debug(f"Saved configuration to {self.config_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False
