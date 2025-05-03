"""NekoConf - Configuration management with web UI."""

# Import public API elements from subpackages
from nekoconf.core.config import NekoConfigManager
from nekoconf.core.eval import NekoSchemaValidator
from nekoconf.core.helper import NekoConfigClient
from nekoconf.server.app import NekoConfigServer

from ._version import __version__

__all__ = [
    "NekoConfigManager",
    "NekoConfigServer",
    "NekoConfigClient",
    "NekoSchemaValidator",
    "__version__",
]
