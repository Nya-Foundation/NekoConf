"""NekoConf - Configuration management with web UI."""

import logging

from nekoconf.config_manager import ConfigManager
from nekoconf.web_server import WebServer
from nekoconf.api import ConfigAPI
from nekoconf.schema_validator import SchemaValidator

__version__ = "0.1.0"
__all__ = ["ConfigManager", "WebServer", "ConfigAPI", "SchemaValidator"]

# Set up null handler to avoid "No handler found" warnings
logging.getLogger(__name__).addHandler(logging.NullHandler())
