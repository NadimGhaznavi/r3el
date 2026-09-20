"""Request a structured identification using the discovered MCP tool."""

from r3el.app.Prompt import Prompt


class SubmitIdentificationPrompt(Prompt):
    def __init__(self) -> None:
        super().__init__(
            'Call submit_identification exactly once with title (nonempty text), '
            'year (an integer), and confidence (a number from 0 to 1). '
            'Return the tool call rather than a prose answer.'
        )
