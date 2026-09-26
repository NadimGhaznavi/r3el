"""Discover and invoke the identification tool through stdio MCP."""

from r3el.interface.MCPTools import MCPTools


class IdentificationTools(MCPTools):
    def __init__(self, endpoint: str, attempt_id: str, *, two_parts: bool = False) -> None:
        super().__init__(endpoint, attempt_id, 'submit_two_parts' if two_parts else 'submit_identification')
