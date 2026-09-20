"""Validate a joint proposal and submit a candidate using the shared workflow."""

import math

from jsonschema import Draft202012Validator, ValidationError

from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS
from ax3l.app.snakelab.SubmitSingleValueHandler import SubmitSingleValueHandler


class SubmitPairValuesHandler(SubmitSingleValueHandler):
    def submit(self, payload: dict) -> dict:
        if not isinstance(payload, dict) or set(payload) != {"pair", "value_1", "value_2"}:
            return self._reject("Supply exactly pair, value_1, and value_2.")
        pair = payload["pair"]
        if not isinstance(pair, str) or pair not in PAIR_PARAMETERS:
            return self._reject("pair must be epsilon_pair or reward_pair.")

        changes = []
        descriptions = []
        for index, path in enumerate(PAIR_PARAMETERS[pair], start=1):
            name = f"value_{index}"
            value = payload[name]
            if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
                return self._reject(f"{name} must be a finite JSON number.")
            definition = self._schema
            for key in path:
                definition = definition["properties"][key]
            try:
                Draft202012Validator(definition).validate(value)
            except ValidationError as error:
                return self._reject(f"{name} ({'.'.join(path)}): {error.message}")
            if definition["type"] == "integer":
                value = int(value)
            changes.append((path, value))
            descriptions.append(f"{'.'.join(path)}: {value}")

        return self._submit_changes(changes, f"{pair}: " + ", ".join(descriptions))
