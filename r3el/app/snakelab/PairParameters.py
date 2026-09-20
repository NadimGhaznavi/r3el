"""Schema-backed assignments for joint parameter proposals."""

import json

from ax3l.app.snakelab.SingleParameters import SCHEMA


PAIR_PARAMETERS = {
    "epsilon_pair": (("epsilon", "initial"), ("epsilon", "decay")),
    "reward_pair": (("game", "rewards", "closer_to_food"),
                    ("game", "rewards", "further_from_food")),
}


def pair_instructions(pair: str) -> str:
    lines = [f"Submit two values together for the Ax3l-assigned {pair}."]
    for index, path in enumerate(PAIR_PARAMETERS[pair], start=1):
        field = SCHEMA
        for key in path:
            field = field["properties"][key]
        rules = {key: field[key] for key in (
            "type", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
            "multipleOf", "enum",
        ) if key in field}
        lines.append(f"value_{index} = {'.'.join(path)}: {field['description']} "
                     f"JSON Schema rules: {json.dumps(rules)}")
    return "\n".join(lines)
