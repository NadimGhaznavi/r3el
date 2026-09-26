"""Expose the identification form; R3el owns its validation."""

import os
from typing import Annotated, Any
from mcp.server import MCPServer
from pydantic import Field

from r3el.app.tools.SubmitIdentification import SubmitIdentification
from r3el.app.tools.SubmitMultipleChoice import SubmitMultipleChoice

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


@mcp.tool(description='Submit the matching candidate number, or 0 when no confident choice is possible.')
async def submit_multiple_choice(
    number: Annotated[Any, Field(json_schema_extra={'type': 'integer', 'minimum': 0})],
) -> str:
    return await SubmitMultipleChoice(
        os.environ['R3EL_ZMQ_ENDPOINT'], os.environ['R3EL_ATTEMPT_ID'],
    ).submit(number)


@mcp.tool(description='Submit the movie identification and the two supplied media paths in part order.')
async def submit_two_parts(
    title: Annotated[Any, Field(json_schema_extra={'type': 'string'})],
    year: Annotated[Any, Field(json_schema_extra={'type': 'integer'})],
    confidence: Annotated[Any, Field(json_schema_extra={'type': 'integer', 'minimum': 0, 'maximum': 10})],
    part_one: Annotated[Any, Field(json_schema_extra={'type': 'string'})],
    part_two: Annotated[Any, Field(json_schema_extra={'type': 'string'})],
) -> str:
    return await SubmitIdentification(
        os.environ['R3EL_ZMQ_ENDPOINT'], os.environ['R3EL_ATTEMPT_ID'],
    ).submit(title, year, confidence, part_one=part_one, part_two=part_two)
