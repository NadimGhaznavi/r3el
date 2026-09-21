"""Expose the identification form; R3el owns its validation."""

import os
from typing import Annotated, Any
from mcp.server import MCPServer
from pydantic import Field

from r3el.app.tools.SubmitIdentification import SubmitIdentification

mcp = MCPServer('r3el-identification')


# Advertise types to the model while forwarding values unchanged for server validation.
@mcp.tool(description='Submit the title, year, and confidence for the assigned filename.')
async def submit_identification(
    title: Annotated[Any, Field(json_schema_extra={'type': 'string'})],
    year: Annotated[Any, Field(json_schema_extra={'type': 'integer'})],
    confidence: Annotated[Any, Field(json_schema_extra={'type': 'integer', 'minimum': 0, 'maximum': 10})],
) -> str:
    return await SubmitIdentification(
        os.environ['R3EL_ZMQ_ENDPOINT'], os.environ['R3EL_ATTEMPT_ID'],
    ).submit(title, year, confidence)
