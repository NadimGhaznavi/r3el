"""Give the model the server's form-validation feedback."""

from r3el.app.Prompt import Prompt


class InvalidIdentification(Prompt):
    def __init__(self, reason: str, *, tool_name: str = 'submit_identification') -> None:
        super().__init__('The submission was rejected. Use the reason in the data to correct it '
                         f'and call {tool_name} again.', data={'reason': reason})
