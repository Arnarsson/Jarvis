#!/bin/bash
# Setup jarvis-memory MCP server in Claude Code
#
# Prerequisites:
# - Claude Code CLI installed (code.claude.com)
# - jarvis-mcp package installed: pip install -e mcp/
# - Jarvis server running at http://127.0.0.1:8000

set -e

echo "Configuring jarvis-memory MCP server for Claude Code..."

# Get the project root (parent of mcp/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Add MCP server to Claude Code (local scope = only this workspace)
claude mcp add --transport stdio --scope local \
  --env JARVIS_API_URL=http://127.0.0.1:8000 \
  jarvis-memory -- python -m jarvis_mcp.server

echo ""
echo "Configuration complete!"
echo ""
echo "Verify with: claude mcp list"
echo "You should see 'jarvis-memory' in the list"
echo ""
echo "To test, start a new Claude Code session and try:"
echo "  - Use the search_memory tool to find something"
echo "  - Use the catch_me_up tool for context recovery"
