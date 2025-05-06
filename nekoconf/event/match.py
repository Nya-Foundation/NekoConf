import re
from typing import Dict

import jmespath
from jmespath.exceptions import ParseError


class PathMatcher:
    """Utility class for matching configuration paths against patterns."""

    @staticmethod
    def match(pattern: str, path: str) -> bool:
        """Match a path against a pattern.

        The pattern can use:
        - Exact matching.
        - Global wildcard "*".
        - Simple wildcards for path segments, e.g., "database.*.host".
        - JMESPath expressions for array indexing and more complex selections,
          e.g., "servers[*].port", "servers[0].config".

        Args:
            pattern: The pattern to match against.
            path: The actual concrete path to check.

        Returns:
            True if the path matches the pattern, False otherwise.
        """
        if not pattern and not path:  # Both empty
            return True
        if not pattern or not path:  # One empty, other not
            return False

        if pattern == "*":  # Global wildcard
            return True
        if pattern == path:  # Exact match
            return True

        # Special case from original logic: "database.*" should match "database"
        # This allows a wildcard pattern to match its own base if the path is exactly that base.
        if pattern.endswith(".*"):
            base_pattern = pattern[:-2]
            if path == base_pattern:
                return True
            # The case "database.*" matching "database.host" will be handled by wildcard matching below.

        # Strategy 1: JMESPath for patterns with array notation or complex selectors
        if "[" in pattern or "]" in pattern:  # Indicates potential JMESPath
            try:
                nested_structure = PathMatcher._path_to_nested_structure(path)
                expression = jmespath.compile(pattern)
                result = expression.search(nested_structure)

                if result is None:
                    return False
                if isinstance(result, list):
                    # If the result is an empty list, it means the pattern (e.g., a filter)
                    # found no matching elements. This is a non-match.
                    if not result:  # Empty list
                        return False
                    # If the list contains only None values, it means the queried attribute
                    # was not found in any of the matched structures. This is a non-match
                    # if the pattern implies a specific attribute.
                    return any(x is not None for x in result)
                # For non-list results (e.g., a direct object or a scalar value like True),
                # if it's not None, it's a match.
                return True
            except (
                ParseError,
                ValueError,
            ):  # JMESPath syntax error in pattern, or error during search
                # If JMESPath parsing/evaluation fails, it's a non-match for this strategy.
                return False

        # Strategy 2: Simple wildcard matching for patterns like "*.key" or "service.*.option"
        # These patterns use '*' as a segment wildcard, not involving '[]'.
        elif "*" in pattern:
            return PathMatcher._simple_wildcard_match(pattern, path)

        # If none of the above rules matched (and not an exact match), then it's a non-match.
        return False

    @staticmethod
    def _simple_wildcard_match(pattern: str, path: str) -> bool:
        """Simple wildcard matching for patterns like *.host or database.*.enabled.

        Args:
            pattern: Pattern with * wildcards (e.g., "foo.*.bar").
            path: Path to match against.

        Returns:
            True if the path matches the pattern.
        """
        # Convert glob-like pattern to regex.
        # '*' not at the end of the pattern string (e.g., in "foo.*.bar")
        #   matches one or more characters except '.', representing a single path segment.
        # '*' at the end of the pattern string (e.g., "foo.*")
        #   matches one or more of any character (including '.'), effectively matching the rest of the path.

        pattern_parts = pattern.split(".")
        regex_segments = []

        for i, p_part in enumerate(pattern_parts):
            if p_part == "*":
                if i == len(pattern_parts) - 1:  # Trailing '*'
                    regex_segments.append(".+")  # Matches one or more of any character to the end
                else:
                    # Matches one or more non-dot characters (a single path segment)
                    regex_segments.append("[^\\.]+")
            else:
                regex_segments.append(re.escape(p_part))

        # Construct the full regex pattern
        # Example: "database.*.enabled" -> "^database\\.[^\\.]+\\.enabled$"
        # Example: "database.*"       -> "^database\\..+$"
        # Example: "*.host"           -> "^[^\\.]+\\.host$"
        regex_str = "^" + "\\.".join(regex_segments) + "$"

        return bool(re.match(regex_str, path))

    @staticmethod
    def _path_to_nested_structure(path: str) -> Dict:
        """Convert a path string to a nested dictionary structure for JMESPath evaluation.

        Args:
            path: Path string like "database.servers[0].host" or "simple.key".

        Returns:
            Nested dictionary representing the path.
            Example: "a.b[0].c" -> {"a": {"b": [{"c": True}]}}
                     "a.b"    -> {"a": {"b": True}}
                     "a"      -> {"a": True}
        """
        parts = re.split(r"\.|\[|\]", path)
        parts = [p for p in parts if p]  # Remove empty parts

        result = {}
        current = result

        for i, part in enumerate(parts):
            if part.isdigit():
                # Handle array indices
                idx = int(part)
                parent_key = parts[i - 1]

                # Make sure parent exists and is a list
                if parent_key not in current:
                    current[parent_key] = []

                # Extend the list if needed
                while len(current[parent_key]) <= idx:
                    current[parent_key].append({})

                # Move pointer to the array element
                current = current[parent_key][idx]
            else:
                # Handle regular keys
                if i < len(parts) - 1 and parts[i + 1].isdigit():
                    # Next part is an array index
                    current[part] = []
                elif i == len(parts) - 1:
                    # Last part, set a non-empty value
                    current[part] = True
                else:
                    # Regular nested object
                    current[part] = {}
                    current = current[part]

        return result
