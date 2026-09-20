from typing import Final


class DR3el:
    RAW_LOGS_ENABLED: Final[bool] = False
    HTTP_TIMEOUT_SECONDS: Final[int] = 300

    VERSION: Final[str] = "0.0.0"

    BASE_DIR: Final[str] = "/opt/prod/r3el"

    PORT: Final[int] = 42220

    ZMQ_ENDPOINT: Final[str] = "tcp://127.0.0.1:42221"
