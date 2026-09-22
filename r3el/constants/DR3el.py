from typing import Final


class DR3el:
    RAW_LOGS_ENABLED: Final[bool] = False
    HTTP_TIMEOUT_SECONDS: Final[int] = 300

    VERSION: Final[str] = "0.3.12"

    BASE_DIR: Final[str] = "/opt/prod/r3el"
    FILM_DIR: Final[str] = "/exports/disk1/archive/film"
    MEDIA_DIR: Final[str] = "/exports/disk1/archive/media"
    BATCH_SIZE: Final[int] = 10
    BATCH_SIZES: Final[tuple[int, ...]] = (5, 10)
    NEW_BATCH_URL: Final[str] = "/batches"
    MAX_CONTROL_BODY_BYTES: Final[int] = 16384
    WORKSPACE_REFRESH_SECONDS: Final[int] = 5
    CONTROL_LOGO_URL: Final[str] = "/static/r3el.png"
    MAX_LLM_RETRIES: Final[int] = 2

    PORT: Final[int] = 42220

    ZMQ_ENDPOINT: Final[str] = "tcp://127.0.0.1:42221"
