"""Request an initial proposal for the epsilon pair."""

from ax3l.app.Prompt import Prompt
from ax3l.app.snakelab.SingleParameters import SCHEMA


class FirstContactEpsilonPair(Prompt):
    def __init__(self):
        fields = SCHEMA["properties"]["epsilon"]["properties"]
        super().__init__(
            f"initial: {fields['initial']['description']}\n"
            f"decay: {fields['decay']['description']}\n\n"
            "Tune epsilon initial and decay together. "
            "Initial controls the starting exploration probability. "
            "Decay controls how quickly exploration decreases across episodes; "
            "values closer to 1 preserve exploration longer. "
            "Choose an untested pair that you believe can improve the current golden "
            "high score while keeping all other configuration values fixed. "
            "Either value may remain unchanged, but the pair as a whole must be new. "
            'Call submit_pair_values with {"value_1": number, "value_2": number}, '
            "where value_1 is initial and value_2 is decay."
        )
