# Jarvis MCP Server

MCP (Model Context Protocol) server providing Jarvis memory tools for Claude Code.

## Installation

```bash
pip install -e .
```

## Usage

The MCP server runs with stdio transport for integration with Claude Code:

```bash
jarvis-mcp
```

## Tools

- `search_memory` - Search across all captured screenshots and imported conversations
- `catch_me_up` - Get a summary of recent activity and context
