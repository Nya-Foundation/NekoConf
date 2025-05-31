"""Storage backends for NekoConf configuration management."""

from .base import StorageBackend, StorageError
from .file import FileStorageBackend
from .remote import RemoteStorageBackend

try:
    import requests
    import websocket

    HAS_REMOTE_DEPS = True
except ImportError:
    HAS_REMOTE_DEPS = False

if HAS_REMOTE_DEPS:
    from .remote import RemoteStorageBackend

else:
    # Define a placeholder class that raises ImportError when instantiated
    class RemoteStorageBackend:
        """Placeholder class for RemoteStorageBackend.

        This raises an informative error when remote storage is used without
        remote dependencies installed.
        """

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Remote storage backend requires additional dependencies. "
                "Install them with: pip install nekoconf[remote]"
            )

        pass


__all__ = [
    "StorageBackend",
    "StorageError",
    "FileStorageBackend",
    "RemoteStorageBackend",
    "HAS_REMOTE_DEPS",
]
