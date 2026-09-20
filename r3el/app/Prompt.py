import json


class Prompt:
    def __init__(self, content: str):
        self._content = content

    def to_json(self) -> str:
        return json.dumps({"role": "user", "content": self._content}, ensure_ascii=False)

    @property
    def source_name(self) -> str:
        """Name of the originating module, without its package or .py suffix."""
        return type(self).__module__.rsplit(".", 1)[-1]

    def to_md(self) -> str:
        return self._content
