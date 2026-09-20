"""Explain an illegal proposal to the LLM."""

from ax3l.app.Prompt import Prompt


class InvalidValue(Prompt):
    def __init__(self, reason: str):
        super().__init__(f"Invalid value: {reason} Choose a legal value from the JSON spec and submit it again.")
