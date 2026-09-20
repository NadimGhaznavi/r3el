from typing import Final


class DQwenV:
    GGUF: Final[str] = "Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf"
    MMPROJ: Final[str] = "mmproj-Qwen2.5-VL-3B-Instruct-F16.gguf"
    CONTEXT_SIZE: Final[int] = 8196
    STARTUP_SECONDS: Final[int] = 5
