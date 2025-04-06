"""NekoConf - Configuration management with web UI."""

import logging

from nekoconf.api import ConfigAPI
from nekoconf.config_manager import ConfigManager
from nekoconf.schema_validator import SchemaValidator
from nekoconf.server import NekoConf

__version__ = "0.1.4"
__all__ = ["ConfigManager", "NekoConf", "ConfigAPI", "SchemaValidator"]

# Set up null handler to avoid "No handler found" warnings
logging.getLogger(__name__).addHandler(logging.NullHandler())
