"""HTTP bridge to an OpenAI-compatible local model server."""

import os

import httpx

from r3el.constants.DR3el import DR3el
from r3el.constants.DLlama import DLlama


class LLM:
    @classmethod
    def from_environment(cls) -> 'LLM':
        return cls(os.environ.get('R3EL_LLM_URL', f'http://127.0.0.1:{DLlama.PORT}'))

    def __init__(self, base_url: str) -> None:
        self.url = base_url.rstrip('/') + '/v1/chat/completions'

    async def complete(self, payload: dict) -> str:
        async with httpx.AsyncClient(timeout=DR3el.HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(self.url, json=payload)
            response.raise_for_status()
            return response.text
