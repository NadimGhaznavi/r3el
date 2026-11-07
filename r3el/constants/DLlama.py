"""Default connection to LlamaSrv's independently managed inference service."""

from typing import Final


class DLlama:
    # LlamaSrv serves inference on 51001 and its control panel on 51000.
    PORT: Final[int] = 51001
