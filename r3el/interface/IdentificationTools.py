"""Discover and invoke the identification tool through stdio MCP."""

from r3el.interface.MCPTools import MCPTools


class IdentificationTools(MCPTools):
    def __init__(self, endpoint: str, attempt_id: str) -> None:
        super().__init__(endpoint, attempt_id, 'submit_identification')
