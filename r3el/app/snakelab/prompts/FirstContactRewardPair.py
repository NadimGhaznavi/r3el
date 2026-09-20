"""Request an initial proposal for the distance reward pair."""

from ax3l.app.Prompt import Prompt
from ax3l.app.snakelab.SingleParameters import SCHEMA


class FirstContactRewardPair(Prompt):
    def __init__(self):
        fields = SCHEMA["properties"]["game"]["properties"]["rewards"]["properties"]
        super().__init__(
            f"closer_to_food: {fields['closer_to_food']['description']}\n"
            f"further_from_food: {fields['further_from_food']['description']}\n\n"
            "Tune closer_to_food and further_from_food together. "
            "Their balance determines how strongly the agent is rewarded for moving "
            "toward food versus penalized for moving away. This matters because some "
            "safe paths require temporary detours. "
            "Choose an untested pair that you believe can improve the current golden "
            "high score while keeping all other configuration values fixed. "
            "Either value may remain unchanged, but the pair as a whole must be new. "
            'Call submit_pair_values with {"value_1": integer, "value_2": integer}, '
            "where value_1 is closer_to_food and value_2 is further_from_food."
        )
