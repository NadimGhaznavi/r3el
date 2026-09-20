"""Prepare captured LLM replies for presentation without changing stored data."""

import json
from typing import Any


def reasoning_content(content: str | None) -> str:
    """Read only the first choice's captured reasoning, if present."""
    try:
        value = json.loads(content)["choices"][0]["message"].get("reasoning_content")
    except (TypeError, ValueError, KeyError, IndexError, AttributeError):
        return ""
    return value if isinstance(value, str) else ""


def reply_content(response: dict[str, Any]) -> str:
    message = response["choices"][0]["message"]
    text = message.get("content") or ""
    calls = [f"{call['function']['name']}({call['function']['arguments']})"
             for call in message.get("tool_calls", [])]
    return "\n".join(([text] if text else []) + calls)


def fields(value: Any, path: str = "") -> list[tuple[str, str]]:
    """Keep every response field, identifying nested values by their full path."""
    if isinstance(value, dict) and value:
        return [row for key, item in value.items()
                for row in fields(item, f"{path}.{key}" if path else key)]
    if isinstance(value, list) and value:
        return [row for index, item in enumerate(value)
                for row in fields(item, f"{path}[{index}]")]
    return [(path, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))]
