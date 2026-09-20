"""Explain a duplicate configuration proposal to the LLM."""

from ax3l.app.Prompt import Prompt


class NoDupes(Prompt):
    def __init__(self, reason: str):
        super().__init__(f"{reason}. Choose a different value and submit it again.")
