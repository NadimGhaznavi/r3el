"""Discover and invoke the identification tool through stdio MCP."""

from r3el.interface.MCPTools import MCPTools


class IdentificationTools(MCPTools):
    def __init__(self, endpoint: str, attempt_id: str, *, two_parts: bool = False, tv: bool = False, series: bool = False) -> None:
        super().__init__(endpoint, attempt_id, 'submit_tv' if tv else 'submit_tv_series' if series else 'submit_two_parts' if two_parts else 'submit_identification')

    def restrict_episode_files(self, file_ids: list[int]) -> None:
        """Advertise exactly the file labels supplied to this episode dialogue."""
        episodes = self.definition['function']['parameters']['properties']['episodes']
        episodes['items']['properties']['file_id']['enum'] = file_ids
        episodes['minItems'] = episodes['maxItems'] = len(file_ids)
