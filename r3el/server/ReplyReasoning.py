"""Decode logged model reasoning and render its Markdown for event details."""

import json

from markdown_it import MarkdownIt
from markupsafe import Markup


class ReplyReasoning:
    def __init__(self) -> None:
        # Model output is untrusted: escape embedded HTML and reject unsafe links.
        self._markdown = MarkdownIt('commonmark', {'html': False, 'breaks': True}).enable('table')

    @staticmethod
    def extract(content: str) -> str | None:
        # Replies are recorded before validation, including malformed model output.
        try:
            reply = json.loads(content)
            reasoning = reply['choices'][0]['message'].get('reasoning_content')
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError):
            return None
        return reasoning if isinstance(reasoning, str) else None

    def render(self, payload) -> Markup | None:
        reasoning = self.extract(payload.get('data')) if isinstance(payload, dict) else None
        if not reasoning or not reasoning.strip():
            return None
        return Markup(self._markdown.render(reasoning))
