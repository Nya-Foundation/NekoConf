"""Web server module for NekoConf configuration management.

This module provides a Web UI and REST API for configuration management.
Install with: pip install nekoconf[server]
"""

# Check for server dependencies
try:
    import fastapi
    import jinja2
    import uvicorn

    HAS_SERVER_DEPS = True
except ImportError:
    HAS_SERVER_DEPS = False

# Only import if dependencies are available
if HAS_SERVER_DEPS:
    from .app import NekoConfOrchestrator
else:
    # Define a placeholder class that raises ImportError when instantiated
    class NekoConfOrchestrator:
        """Placeholder class for NekoConfOrchestrator.

        This raises an informative error when server features are used without
        server dependencies installed.
        """

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Web server features require additional dependencies. "
                "Install them with: pip install nekoconf[server]"
            )


__all__ = ["NekoConfOrchestrator", "HAS_SERVER_DEPS"]
