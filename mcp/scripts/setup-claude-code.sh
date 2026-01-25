#!/bin/bash
# Setup jarvis-memory MCP server in Claude Code
#
# Prerequisites:
# - Claude Code CLI installed (code.claude.com)
# - Jarvis server running at http://127.0.0.1:8000

set -e

# Get the project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MCP_DIR="$(dirname "$SCRIPT_DIR")"

# Create venv and install if needed
if [ ! -d "$MCP_DIR/.venv" ]; then
  echo "Creating virtual environment..."
  python -m venv "$MCP_DIR/.venv"
  echo "Installing jarvis-mcp..."
  "$MCP_DIR/.venv/bin/pip" install -e "$MCP_DIR"
fi

PYTHON="$MCP_DIR/.venv/bin/python"

echo "Configuring jarvis-memory MCP server for Claude Code..."

# Add MCP server to Claude Code (local scope = only this workspace)
claude mcp add --transport stdio --scope local \
  --env JARVIS_API_URL=http://127.0.0.1:8000 \
  jarvis-memory -- "$PYTHON" -m jarvis_mcp.server

echo ""
echo "Configuration complete!"
echo ""
echo "Verify with: claude mcp list"
echo "You should see 'jarvis-memory' in the list"
echo ""
echo "To test, start a new Claude Code session and try:"
echo "  - Use the search_memory tool to find something"
echo "  - Use the catch_me_up tool for context recovery"
