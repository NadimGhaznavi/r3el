from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ax3l.constants.DAx3l import DAx3l


class LLM:
    """Send inference requests and return the unparsed HTTP response."""

    def __init__(self, base_url: str):
        self.url = base_url.rstrip("/") + "/v1/chat/completions"

    def complete(self, payload: bytes) -> tuple[int, str, bytes]:
        request = Request(
            self.url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            response = urlopen(request, timeout=DAx3l.HTTP_TIMEOUT_SECONDS)
        except HTTPError as error:
            response = error
        with response:
            return response.status, str(response.headers), response.read()
