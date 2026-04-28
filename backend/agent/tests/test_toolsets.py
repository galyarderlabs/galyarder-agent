"""Test cases for the G-Agent toolset resolver."""

import pytest
from g_agent.agent.tools.registry import ToolRegistry
from g_agent.agent.tools.toolsets import ToolsetResolver


@pytest.fixture
def registry():
    """Mock registry with some standard tools and MCP tools."""
    r = ToolRegistry()
    
    # We mock tools by just defining their names
    class MockTool:
        def __init__(self, name):
            self._name = name
        @property
        def name(self):
            return self._name
        def execute(self, *args, **kwargs):
            pass
    
    tools = [
        "web_search", "web_extract", "web_fetch", 
        "exec", "process", "read_file", "write_file", 
        "edit_file", "list_dir", "remember", "recall", 
        "update_profile", "session_search", "skill_manage",
        "mcp_github_create_issue", "mcp_github_list_issues",
        "mcp_linear_get_issue"
    ]
    for t in tools:
        r.register(MockTool(t))
        
    return r


def test_toolset_resolution_basic(registry):
    resolver = ToolsetResolver(registry)
    tools = resolver.resolve_toolset("web")
    
    # 'web' toolset has: web_search, web_extract, web_fetch
    assert "web_search" in tools
    assert "web_extract" in tools
    assert "web_fetch" in tools


def test_toolset_resolution_with_includes(registry):
    resolver = ToolsetResolver(registry)
    
    # 'browser' includes 'web'
    tools = resolver.resolve_toolset("browser")
    
    # Direct tools
    assert "browser_open" in tools
    # Included tools
    assert "web_search" in tools
    assert "web_fetch" in tools


def test_toolset_resolution_all(registry):
    resolver = ToolsetResolver(registry)
    tools = resolver.resolve_toolset("all")
    
    # Should include all statically defined tools and dynamic MCP ones
    assert "web_search" in tools
    assert "read_file" in tools
    assert "exec" in tools


def test_toolset_resolution_mcp_dynamic(registry):
    resolver = ToolsetResolver(registry)
    
    # Check that dynamic toolset resolution for MCP works
    names = resolver.get_toolset_names()
    assert "github" in names
    assert "linear" in names
    
    # Resolve the virtual 'github' toolset
    github_tools = resolver.resolve_toolset("github")
    assert "mcp_github_create_issue" in github_tools
    assert "mcp_github_list_issues" in github_tools
    assert "mcp_linear_get_issue" not in github_tools


def test_multiple_toolsets(registry):
    resolver = ToolsetResolver(registry)
    tools = resolver.resolve_multiple_toolsets(["web", "terminal"])
    
    assert "web_search" in tools
    assert "exec" in tools
    assert "read_file" not in tools  # belongs to file toolset


def test_invalid_toolset(registry):
    resolver = ToolsetResolver(registry)
    tools = resolver.resolve_toolset("does_not_exist")
    assert tools == []


def test_single_tool_resolution(registry):
    resolver = ToolsetResolver(registry)
    # When passed an exact tool name, it should resolve to just that tool
    tools = resolver.resolve_toolset("read_file")
    assert tools == ["read_file"]
