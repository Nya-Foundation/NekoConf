"""NekoConf - Configuration management for Python applications.

NekoConf is a dynamic configuration manager with support for multiple file formats,
environment variable overrides, and schema validation.
"""

from ._version import __version__

# Always import core features (minimal dependencies)
from .core.config import NekoConfigManager
from .core.wrapper import NekoConfigWrapper
from .event.pipeline import EventType

# Import optional features only if dependencies are installed
# Remote functionality
try:
    from .remote import HAS_REMOTE_DEPS, RemoteConfigClient
except ImportError:
    HAS_REMOTE_DEPS = False

# Schema validation
try:
    from .schema import HAS_SCHEMA_DEPS, NekoSchemaValidator
except ImportError:
    HAS_SCHEMA_DEPS = False

# Server functionality
try:
    from .server import HAS_SERVER_DEPS, NekoConfigServer
except ImportError:
    HAS_SERVER_DEPS = False

# Expose core API
__all__ = [
    "__version__",
    "NekoConfigManager",
    "NekoConfigWrapper",
    "EventType",
]

# Add optional components if available
if HAS_REMOTE_DEPS:
    __all__.append("RemoteConfigClient")

if HAS_SCHEMA_DEPS:
    __all__.append("NekoSchemaValidator")

if HAS_SERVER_DEPS:
    __all__.append("NekoConfigServer")
