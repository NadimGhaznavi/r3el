from typing import Final


class DR3el:
    RAW_LOGS_ENABLED: Final[bool] = False
    HTTP_TIMEOUT_SECONDS: Final[int] = 300

    VERSION: Final[str] = "1.0.5"

    BASE_DIR: Final[str] = "/opt/prod/r3el"
    FILM_DIR: Final[str] = "/exports/disk1/archive/film"
    MEDIA_DIR: Final[str] = "/exports/disk1/archive/media"
    PROCESSING_GROUP_SIZE: Final[int] = 10
    BATCH_SIZE: Final[int] = 10
    MAX_BATCH_SIZE: Final[int] = 4294967295
    STOP_BATCH_URL: Final[str] = '/workspace/stop'
    NEW_BATCH_URL: Final[str] = "/batches"
    FILE_ACTION_URL: Final[str] = "/workspace/actions"
    MATCH_TMDB_URL: Final[str] = "/workspace/match"
    AUTO_APPROVE_CONFIDENCE: Final[int] = 10
    MAX_CONTROL_BODY_BYTES: Final[int] = 16384
    CONTROL_LOGO_URL: Final[str] = "/static/r3el.png"
    MAX_LLM_RETRIES: Final[int] = 2
    MAX_IDENTIFICATION_RETRIES: Final[int] = 3

    PORT: Final[int] = 42220

    ZMQ_ENDPOINT: Final[str] = "tcp://127.0.0.1:42221"
