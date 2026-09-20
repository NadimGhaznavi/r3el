from typing import Final

class DLlama:
    BASE_DIR: Final[str] = "/opt/prod/llama.cpp"
    BIN_DIR: Final[str] = "bin"
    SERVER: Final[str] = "llama-server"

    MODEL_DIR: Final[str] = "/opt/prod/models"

    HOST: Final[str] = "0.0.0.0"
    PORT: Final[int] = 27770
    PORT_DEV: Final[int] = 27768
    PORT_QA: Final[int] = 27769
