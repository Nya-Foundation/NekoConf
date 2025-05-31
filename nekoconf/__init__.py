"""
NekoConf is a dynamic configuration manager with support for multiple file formats,
environment variable overrides, and schema validation.
"""

from ._version import __version__

# Always import core features (minimal dependencies)
from .core.config import NekoConf
from .event.pipeline import EventType
from .storage import (
    FileStorageBackend,
    StorageBackend,
)

# Import optional features only if dependencies are installed
# Remote functionality
try:
    from .storage import HAS_REMOTE_DEPS, RemoteStorageBackend
except ImportError as e:
    HAS_REMOTE_DEPS = False

# Schema validation
try:
    from .schema import HAS_SCHEMA_DEPS, NekoSchemaValidator
except ImportError:
    HAS_SCHEMA_DEPS = False

# Server functionality
try:
    from .server import HAS_SERVER_DEPS, NekoConfOrchestrator
except ImportError:
    HAS_SERVER_DEPS = False

# Expose core API
__all__ = [
    "__version__",
    "NekoConf",
    "EventType",
    "StorageBackend",
    "FileStorageBackend",
]

# Add optional components if available
if HAS_REMOTE_DEPS:
    __all__.append("RemoteStorageBackend")

if HAS_SCHEMA_DEPS:
    __all__.append("NekoSchemaValidator")

if HAS_SERVER_DEPS:
    __all__.append("NekoConfOrchestrator")
