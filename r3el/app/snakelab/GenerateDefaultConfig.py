"""Build a simulation configuration from the defaults in the JSON spec."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator


class GenerateDefaultConfig:
    def run(self) -> dict:
        schema = json.loads(
            Path(__file__).with_name("simulation-config-v2.schema.json").read_text(
                encoding="utf-8"
            )
        )

        def defaults(node):
            if node["type"] == "object":
                return {name: defaults(child) for name, child in node["properties"].items()}
            return node["default"]

        config = defaults(schema)
        Draft202012Validator(schema).validate(config)
        return config
