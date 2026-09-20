"""Request a value for the assigned parameter."""

from ax3l.app.Prompt import Prompt
from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS


class ComparisonSingle(Prompt):
    def __init__(self, parameter):
        super().__init__(
            f"{parameter}: {SINGLE_PARAMETERS[parameter][1]['description']}\n\n"
            f"Choose an untested {parameter} value to improve the current golden high score. "
            'Call submit_single_value with {"value": number}.'
        )
