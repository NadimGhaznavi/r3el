"""Use MCP for tool discovery/calls; the tool forwards actions to Ax3l over ZMQ."""

from copy import deepcopy
import json
from pathlib import Path
import sys

from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS
from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS
from ax3l.constants.DSnakeLab import DSnakeLab

from mcp import Client
from mcp.client.stdio import StdioServerParameters


class SnakeLabTools:
    def __init__(self, endpoint: str, parameter: str):
        if parameter not in SINGLE_PARAMETERS and parameter not in PAIR_PARAMETERS:
            raise ValueError(f"Unknown conversation parameter: {parameter}")
        self._tool_name = ("submit_pair_values" if parameter in PAIR_PARAMETERS
                           else "submit_single_value")
        root = Path(__file__).resolve().parents[2]
        self._client = Client(StdioServerParameters(
            command=sys.executable, args=["-m", "ax3l.app.snakelab.tools"], cwd=str(root),
            env={"PYTHONPATH": str(root), "AX3L_ZMQ_ENDPOINT": endpoint,
                 "AX3L_CONVERSATION_PARAMETER": parameter,
                 "PYTHONDONTWRITEBYTECODE": "1"},
        ), read_timeout_seconds=DSnakeLab.MCP_TIMEOUT_SECONDS)

    async def __aenter__(self):
        await self._client.__aenter__()
        try:
            tools = await self._client.list_tools()
            tool = next(tool for tool in tools.tools if tool.name == self._tool_name)
            schema = deepcopy(tool.input_schema)
            self.definition = {"type": "function", "function": {
                "name": tool.name, "description": tool.description, "parameters": schema,
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
            raise RuntimeError("MCP tool failed; submission may have occurred. Do not automatically retry.")
        return json.loads(result.content[0].text)
