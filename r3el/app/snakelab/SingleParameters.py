"""Schema-backed search space for single-parameter proposals."""

import json
from pathlib import Path

SCHEMA = json.loads(
    Path(__file__).with_name("simulation-config-v2.schema.json").read_text()
)
EXCLUDED = {"seed", "closer_to_food", "further_from_food", "initial", "decay"}


def _fields(node, path=()):
    for name, field in node["properties"].items():
        if field["type"] == "object":
            yield from _fields(field, path + (name,))
        elif name not in EXCLUDED and "const" not in field:
            yield name, (path + (name,), field)


SINGLE_PARAMETERS = dict(_fields(SCHEMA))


def parameter_instructions(parameter=None):
    names = list(SINGLE_PARAMETERS) if parameter is None else [parameter]
    lines = []
    for name in names:
        _, field = SINGLE_PARAMETERS[name]
        rules = {
            key: value
            for key, value in field.items()
            if key
            in (
                "type",
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
                "multipleOf",
                "enum",
            )
        }
        lines.append(f"{name}: JSON Schema rules: {json.dumps(rules)}")
    return "\n".join(lines)
