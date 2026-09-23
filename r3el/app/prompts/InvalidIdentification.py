"""Give the model the server's form-validation feedback."""

from r3el.app.Prompt import Prompt


class InvalidIdentification(Prompt):
    def __init__(self, reason: str) -> None:
        super().__init__('The submission was rejected. Use the reason in the data to correct it '
                         'and call submit_identification again.', data={'reason': reason})
