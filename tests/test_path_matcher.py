"""Test cases for the PathMatcher class."""

import pytest

from nekoconf.event.match import PathMatcher


class TestPathMatcher:
    """Test cases for PathMatcher functionality."""

    def test_exact_match(self):
        """Test exact path matching."""
        assert PathMatcher.match("database.host", "database.host") is True
        assert PathMatcher.match("database.host", "database.port") is False
        assert PathMatcher.match("server.config", "server.config") is True

    def test_wildcard_match(self):
        """Test wildcard path matching."""
        # Global wildcard
        assert PathMatcher.match("*", "database.host") is True
        assert PathMatcher.match("*", "any.path.here") is True

        # Path segment wildcard
        assert PathMatcher.match("database.*", "database.host") is True
        assert PathMatcher.match("database.*", "database.port") is True
        assert PathMatcher.match("database.*", "database") is True
        assert PathMatcher.match("database.*", "other.host") is False

        # Multiple wildcards
        assert PathMatcher.match("*.host", "database.host") is True
        assert PathMatcher.match("*.host", "server.host") is True
        assert PathMatcher.match("*.host", "database.port") is False

    def test_nested_wildcard_match(self):
        """Test nested wildcard path matching."""
        assert PathMatcher.match("database.*.enabled", "database.primary.enabled") is True
        assert PathMatcher.match("database.*.enabled", "database.replica.enabled") is True
        assert PathMatcher.match("database.*.enabled", "database.primary.host") is False
        assert PathMatcher.match("servers.*.ports.*", "servers.web.ports.http") is True

    def test_array_notation(self):
        """Test array notation in path matching."""
        assert PathMatcher.match("servers[0]", "servers[0]") is True
        assert PathMatcher.match("servers[*]", "servers[0]") is True
        assert PathMatcher.match("servers[*]", "servers[1]") is True
        assert PathMatcher.match("servers[*].host", "servers[0].host") is True
        assert PathMatcher.match("servers[*].host", "servers[5].host") is True
        assert PathMatcher.match("servers[*].host", "servers[0].port") is False

    def test_complex_patterns(self):
        """Test more complex matching patterns."""
        assert (
            PathMatcher.match(
                "database[*].connections[*].status", "database[0].connections[1].status"
            )
            is True
        )
        assert PathMatcher.match("users[*].address.city", "users[5].address.city") is True
        assert PathMatcher.match("config.*.options[*]", "config.section1.options[3]") is True
        assert PathMatcher.match("logs[*].entries[*].level", "logs[2].entries[10].level") is True

    def test_edge_cases(self):
        """Test edge cases for path matching."""
        # Empty patterns
        assert PathMatcher.match("", "") is True
        assert PathMatcher.match("", "path") is False
        assert PathMatcher.match("path", "") is False

        # Pattern is a subset of the path
        assert PathMatcher.match("database", "database.host") is False

        # Path is a parent of a pattern with wildcard
        assert PathMatcher.match("database.host.*", "database.host") is True

    def test_jmespath_expressions(self):
        """Test dot notation in the pattern."""
        assert PathMatcher.match("database.servers[0]", "database.servers[0]") is True
        assert PathMatcher.match("database.servers[0].host", "database.servers[0].host") is True

        # These should work with the JMESPath evaluation
        assert PathMatcher.match("servers[*].config", "servers[2].config") is True
        assert PathMatcher.match("users[*].roles[*]", "users[1].roles[3]") is True
