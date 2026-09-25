"""MCP access point — turtleOS reachable from any MCP client.

Design: ``docs/design/mcp-access-point.md``. This package must not import
Discord or any module that does; ``tests/test_mcp_access.py`` imports it in a
clean interpreter and fails if ``discord`` appears in ``sys.modules``.
"""
