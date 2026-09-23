"""Discover and invoke the requested tool through a stdio MCP subprocess."""

from copy import deepcopy
import json
from pathlib import Path
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


class MCPTools:
    def __init__(self, endpoint: str, attempt_id: str, tool_name: str) -> None:
        self._tool_name = tool_name
        root = Path(__file__).resolve().parents[2]
        self._client = Client(StdioServerParameters(
            command=sys.executable, args=['-B', '-m', 'r3el.app.tools'], cwd=str(root),
            env={'PYTHONPATH': str(root), 'R3EL_ZMQ_ENDPOINT': endpoint,
                 'R3EL_ATTEMPT_ID': attempt_id, 'PYTHONDONTWRITEBYTECODE': '1'},
        ), read_timeout_seconds=30)

    async def __aenter__(self):
        await self._client.__aenter__()
        try:
            tools = await self._client.list_tools()
            tool = next(tool for tool in tools.tools if tool.name == self._tool_name)
            self.definition = {'type': 'function', 'function': {
                'name': tool.name, 'description': tool.description,
                'parameters': deepcopy(tool.input_schema),
            }}
        except BaseException:
            await self._client.__aexit__(*sys.exc_info())
            raise
        return self

    async def __aexit__(self, *exc):
        return await self._client.__aexit__(*exc)

    async def submit(self, arguments: dict) -> dict:
        result = await self._client.call_tool(self._tool_name, arguments)
        if result.is_error:
            raise RuntimeError('MCP execution failed; do not retry an uncertain submission.')
        return json.loads(result.content[0].text)
