"""Helper utilities for NekoConf tests."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict

import yaml


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
