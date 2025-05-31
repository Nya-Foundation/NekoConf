from typing import List

from ..utils.helper import parse_path


class PathMatcher:
    """Simple and elegant path matching using Python's power."""

    @staticmethod
    def match(pattern: str, path: str) -> bool:
        """Match a path against a pattern using enhanced dot notation.

        The pattern can use:
        - Exact matching: "database.host" matches "database.host"
        - Global wildcard "*": matches any path
        - Segment wildcards: "database.*.host" matches "database.redis.host"
        - Array index matching: "servers[0].host" matches "servers[0].host"
        - Mixed patterns: "apps[*].config.*.port" matches "apps[0].config.redis.port"

        Args:
            pattern: The pattern to match against
            path: The actual concrete path to check

        Returns:
            True if the path matches the pattern, False otherwise
        """
        if not pattern and not path:
            return True
        if not pattern or not path:
            return False
        if pattern == "*":
            return True
        if pattern == path:
            return True

        # Parse both pattern and path into segments
        pattern_segments = parse_path(pattern)
        path_segments = parse_path(path)

        # Handle prefix matching for patterns ending with "*"
        if pattern.endswith(".*"):
            # Remove the trailing "*" and check if path starts with pattern prefix
            prefix_segments = pattern_segments[:-1]
            return len(path_segments) >= len(prefix_segments) and PathMatcher._segments_match(
                prefix_segments, path_segments[: len(prefix_segments)]
            )

        # Exact segment count matching
        if len(pattern_segments) != len(path_segments):
            return False

        return PathMatcher._segments_match(pattern_segments, path_segments)

    @staticmethod
    def _segments_match(pattern_segments: List[str], path_segments: List[str]) -> bool:
        """Match pattern segments against path segments."""
        return all(
            pattern_seg == "*" or pattern_seg == path_seg
            for pattern_seg, path_seg in zip(pattern_segments, path_segments)
        )
