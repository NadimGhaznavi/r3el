"""Application-level ZeroMQ routing and response names."""

from typing import Final


class DMessage:
    SERVER: Final[str] = 'r3el'
    CONTROL: Final[str] = 'r3el-control'
    MCP_IDENTIFICATION: Final[str] = 'mcp-identification'
    IDENTIFICATION: Final[str] = 'identification'
    SUBMIT_IDENTIFICATION: Final[str] = 'submit_identification'
    BATCH: Final[str] = 'batch'
    NEW_BATCH: Final[str] = 'new_batch'

    ACCEPTED: Final[str] = 'accepted'
    BUSY: Final[str] = 'busy'
    ERROR: Final[str] = 'error'
    INVALID_PARAMETERS: Final[str] = 'invalid_parameters'
    UNKNOWN_REQUEST: Final[str] = 'unknown_request'
    UNAVAILABLE: Final[str] = 'unavailable'
    NOT_CONFIGURED: Final[str] = 'not_configured'
