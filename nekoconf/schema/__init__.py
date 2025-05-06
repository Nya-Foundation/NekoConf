"""Schema validation module for NekoConf.

This module provides JSON schema validation functionality for configuration files.
Install with: pip install nekoconf[schema]
"""

# Check for schema dependencies
try:
    import jsonschema
    import rfc3987

    HAS_SCHEMA_DEPS = True
except ImportError:
    HAS_SCHEMA_DEPS = False

# Only import if dependencies are available
if HAS_SCHEMA_DEPS:
    from .validator import NekoSchemaValidator
else:
    # Define a placeholder class that raises ImportError when instantiated
    class NekoSchemaValidator:
        """Placeholder class for NekoSchemaValidator.

        This raises an informative error when schema validation is used without
        schema dependencies installed.
        """

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Schema validation requires additional dependencies. "
                "Install them with: pip install nekoconf[schema]"
            )


__all__ = ["NekoSchemaValidator", "HAS_SCHEMA_DEPS"]
