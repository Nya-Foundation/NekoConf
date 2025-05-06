"""Remote configuration sync module for NekoConf.

This module provides functionality to synchronize configuration with a remote NekoConf server.
Install with: pip install nekoconf[remote]
"""

# Check for remote dependencies
try:
    import requests
    import websocket

    HAS_REMOTE_DEPS = True
except ImportError as e:
    print(f"Remote dependencies not found. Remote sync functionality will be disabled., {e}")
    HAS_REMOTE_DEPS = False

# Only import if dependencies are available
if HAS_REMOTE_DEPS:
    from .client import RemoteConfigClient
else:
    # Define a placeholder class that raises ImportError when instantiated
    class RemoteConfigClient:
        """Placeholder class for RemoteConfigClient.

        This raises an informative error when remote sync is used without
        remote dependencies installed.
        """

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Remote sync requires additional dependencies. "
                "Install them with: pip install nekoconf[remote]"
            )


__all__ = ["RemoteConfigClient", "HAS_REMOTE_DEPS"]
