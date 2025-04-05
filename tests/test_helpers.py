"""Helper utilities for NekoConf tests."""

import asyncio
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable, Awaitable


class BaseObserver:
    """Base class for observer implementations."""

    def __init__(self):
        self.called = False
        self.data = None
        # Add __name__ attribute to make the observer identifiable
        self.__name__ = self.__class__.__name__

    def reset(self):
        """Reset the observer state."""
        self.called = False
        self.data = None


class SyncObserver(BaseObserver):
    """A synchronous observer for testing configuration changes."""

    def __call__(self, config_data):
        """Called when configuration changes."""
        self.called = True
        self.data = config_data


class AsyncObserver(BaseObserver):
    """An asynchronous observer for testing configuration changes."""

    async def __call__(self, config_data):
        """Called when configuration changes."""
        await asyncio.sleep(0.01)  # Simulate async work
        self.called = True
        self.data = config_data


def create_failing_observer(error_message: str = "Test error"):
    """Create an observer that raises an exception when called."""

    def observer(config_data):
        raise Exception(error_message)

    return observer


async def create_async_failing_observer(error_message: str = "Test async error"):
    """Create an async observer that raises an exception when called."""

    async def observer(config_data):
        await asyncio.sleep(0.01)
        raise Exception(error_message)

    return observer


async def wait_for_observers(timeout=0.2) -> None:
    """Wait for all async observer tasks to complete.

    Args:
        timeout: Time to wait for pending tasks
    """
    # Allow the event loop to process any pending tasks
    await asyncio.sleep(timeout)


class ConfigTestHelper:
    """Helper class for common configuration testing tasks."""

    @staticmethod
    def get_example_configs() -> Dict[str, Path]:
        """Get all example configuration files from the examples directory."""
        examples_dir = Path(__file__).parent.parent / "examples"
        if not examples_dir.exists():
            return {}

        configs = {}
        for file_path in examples_dir.glob("*.y*ml"):
            configs[file_path.stem] = file_path
        for file_path in examples_dir.glob("*.json"):
            configs[file_path.stem] = file_path
        return configs

    @staticmethod
    def get_example_schemas() -> Dict[str, Path]:
        """Get all example schema files from the examples directory."""
        examples_dir = Path(__file__).parent.parent / "examples"
        if not examples_dir.exists():
            return {}

        schemas = {}
        for file_path in examples_dir.glob("*_schema.json"):
            name = file_path.stem.replace("_schema", "")
            schemas[name] = file_path
        return schemas

    @staticmethod
    def create_temp_config(tmp_path: Path, data: Dict) -> Path:
        """Create a temporary YAML configuration file."""
        config_path = tmp_path / "config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(data, f)
        return config_path

    @staticmethod
    def create_temp_json_config(tmp_path: Path, data: Dict) -> Path:
        """Create a temporary JSON configuration file."""
        config_path = tmp_path / "config.json"
        with open(config_path, "w") as f:
            json.dump(data, f)
        return config_path

    @staticmethod
    def create_temp_schema(tmp_path: Path, schema: Dict) -> Path:
        """Create a temporary schema file."""
        schema_path = tmp_path / "schema.json"
        with open(schema_path, "w") as f:
            json.dump(schema, f)
        return schema_path
