"""Register SnakeLab tools here; Ax3l owns validation and submission."""

from mcp.server import MCPServer
import os
from pydantic import StrictFloat, StrictInt

from ax3l.app.snakelab.tools.SubmitSingleValue import SubmitSingleValue
from ax3l.app.snakelab.tools.SubmitPairValues import SubmitPairValues
from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS, pair_instructions
from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS, parameter_instructions
from ax3l.constants.DAx3l import DAx3l


mcp = MCPServer("snakelab")


parameter = os.environ.get("AX3L_CONVERSATION_PARAMETER")
description = (f"Submit a new {parameter} value.\n{parameter_instructions(parameter)}"
               if parameter in SINGLE_PARAMETERS else "Submit a value for the Ax3l-assigned parameter.")


@mcp.tool(description=description)
async def submit_single_value(value: StrictInt | StrictFloat) -> str:
    endpoint = os.environ.get("AX3L_ZMQ_ENDPOINT", DAx3l.ZMQ_ENDPOINT)
    if parameter not in SINGLE_PARAMETERS:
        raise ValueError("Ax3l must assign a valid conversation parameter before submission")
    return await SubmitSingleValue(endpoint).submit(parameter, value)


pair_description = (pair_instructions(parameter) if parameter in PAIR_PARAMETERS
                    else "Submit two values for the Ax3l-assigned parameter pair.")


@mcp.tool(description=pair_description)
async def submit_pair_values(value_1: StrictInt | StrictFloat,
                             value_2: StrictInt | StrictFloat) -> str:
    endpoint = os.environ.get("AX3L_ZMQ_ENDPOINT", DAx3l.ZMQ_ENDPOINT)
    if parameter not in PAIR_PARAMETERS:
        raise ValueError("Ax3l must assign a valid conversation pair before submission")
    return await SubmitPairValues(endpoint).submit(parameter, value_1, value_2)
