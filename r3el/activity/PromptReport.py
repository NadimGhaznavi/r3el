"""Present the exact text and PNG snapshots captured in prompt events."""

import re


def parts(message: dict) -> list[dict]:
    content = message["content"]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    result = []
    for part in content:
        if part["type"] == "text":
            result.append({"type": "text", "text": part["text"]})
        elif part["type"] == "image_url":
            url = part["image_url"]["url"]
            if not re.fullmatch(r"data:image/png;base64,[A-Za-z0-9+/]+={0,2}", url):
                raise ValueError("Prompt report requires an embedded PNG")
            result.append({"type": "image", "url": url})
        else:
            raise ValueError(f"Unsupported prompt content: {part['type']}")
    return result


def summary(message: dict) -> str:
    content = message["content"]
    if isinstance(content, str):
        return content
    text = "\n".join(part["text"] for part in content if part["type"] == "text")
    return text or "View plot prompt"
