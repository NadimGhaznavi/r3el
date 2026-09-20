"""Run the SnakeLab MCP server over stdio for llama-server."""

from ax3l.app.snakelab.tools.server import mcp


if __name__ == "__main__":
    mcp.run()
