from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class LLMHealth:
    def status(self, url: str) -> dict:
        try:
            with urlopen(url, timeout=3) as response:
                return {"healthy": response.status == 200, "http_status": response.status}
        except HTTPError as error:
            return {"healthy": False, "http_status": error.code}
        except (URLError, TimeoutError) as error:
            return {"healthy": False, "error": str(error)}
