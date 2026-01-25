"""Unit tests for MCP tool registration.

Tests that tools are properly registered with the MCP server
and have correct parameter schemas.
"""

import pytest


class TestToolRegistration:
    """Tests for tool registration with MCP server."""

    @pytest.fixture
    def mcp_server(self):
        """Get the MCP server instance."""
        from jarvis_mcp.server import mcp
        return mcp

    def test_search_memory_registered(self, mcp_server):
        """search_memory tool should be registered."""
        # Get list of registered tools
        tools = mcp_server._tool_manager._tools
        assert "search_memory" in tools

    def test_catch_me_up_registered(self, mcp_server):
        """catch_me_up tool should be registered."""
        tools = mcp_server._tool_manager._tools
        assert "catch_me_up" in tools

    def test_search_memory_has_query_parameter(self, mcp_server):
        """search_memory should have query parameter."""
        tools = mcp_server._tool_manager._tools
        tool = tools["search_memory"]
        # Tool function is stored, check its schema via the tool definition
        schema = tool.parameters
        assert "query" in schema["properties"]
        assert schema["properties"]["query"]["type"] == "string"

    def test_search_memory_has_limit_parameter(self, mcp_server):
        """search_memory should have limit parameter."""
        tools = mcp_server._tool_manager._tools
        tool = tools["search_memory"]
        schema = tool.parameters
        assert "limit" in schema["properties"]
        assert schema["properties"]["limit"]["type"] == "integer"

    def test_search_memory_has_sources_parameter(self, mcp_server):
        """search_memory should have sources parameter."""
        tools = mcp_server._tool_manager._tools
        tool = tools["search_memory"]
        schema = tool.parameters
        assert "sources" in schema["properties"]

    def test_catch_me_up_has_topic_parameter(self, mcp_server):
        """catch_me_up should have topic parameter."""
        tools = mcp_server._tool_manager._tools
        tool = tools["catch_me_up"]
        schema = tool.parameters
        assert "topic" in schema["properties"]
        assert schema["properties"]["topic"]["type"] == "string"

    def test_catch_me_up_has_days_parameter(self, mcp_server):
        """catch_me_up should have days parameter."""
        tools = mcp_server._tool_manager._tools
        tool = tools["catch_me_up"]
        schema = tool.parameters
        assert "days" in schema["properties"]
        assert schema["properties"]["days"]["type"] == "integer"

    def test_search_memory_has_description(self, mcp_server):
        """search_memory should have a description."""
        tools = mcp_server._tool_manager._tools
        tool = tools["search_memory"]
        assert tool.description is not None
        assert len(tool.description) > 10  # Has meaningful description

    def test_catch_me_up_has_description(self, mcp_server):
        """catch_me_up should have a description."""
        tools = mcp_server._tool_manager._tools
        tool = tools["catch_me_up"]
        assert tool.description is not None
        assert len(tool.description) > 10  # Has meaningful description

    def test_search_memory_query_has_constraints(self, mcp_server):
        """search_memory query should have min/max length."""
        tools = mcp_server._tool_manager._tools
        tool = tools["search_memory"]
        schema = tool.parameters
        query_schema = schema["properties"]["query"]
        assert query_schema.get("minLength") == 1
        assert query_schema.get("maxLength") == 1000

    def test_catch_me_up_days_has_constraints(self, mcp_server):
        """catch_me_up days should have min/max values."""
        tools = mcp_server._tool_manager._tools
        tool = tools["catch_me_up"]
        schema = tool.parameters
        days_schema = schema["properties"]["days"]
        assert days_schema.get("minimum") == 1
        assert days_schema.get("maximum") == 30
