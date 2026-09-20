"""Validate one proposed change to the golden config and submit unique candidates."""

from copy import deepcopy
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS
from ax3l.app.DbMgr import DbMgr
from ax3l.app.EventLogDb import EventLogDb
from ax3l.app.snakelab.prompts.InvalidValue import InvalidValue
from ax3l.app.snakelab.prompts.NoDupes import NoDupes
from ax3l.constants.DEventCategory import DEventCategory
from ax3l.constants.DAx3l import DAx3l
from ax3l.interface.SnakeLab import SnakeLab


class SubmitSingleValueHandler:
    def __init__(self, db: DbMgr):
        self._db = db
        self._snake = SnakeLab()
        self._schema = json.loads(Path(__file__).with_name("simulation-config-v2.schema.json").read_text())

    def _reject(self, reason: str, *, duplicate: bool = False) -> dict:
        category = DEventCategory.Configuration
        prompt = NoDupes(reason) if duplicate else InvalidValue(reason)
        self._db.log(
            category.PROPOSAL_DUPLICATE if duplicate else category.PROPOSAL_INVALID,
            category.CATEGORY, "INFO", prompt.to_md(),
        )
        return {"status": "rejected", "reason": reason,
                "code": "duplicate_config" if duplicate else "invalid_value",
                "prompt": json.loads(prompt.to_json()), "source_name": prompt.source_name}

    def submit(self, payload: dict) -> dict:
        if set(payload) != {"parameter", "value"}:
            return self._reject("Supply exactly parameter and value.")
        parameter, value = payload["parameter"], payload["value"]
        if not isinstance(parameter, str) or not parameter:
            return self._reject("parameter must be a JSON spec key.")
        if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
            return self._reject("value must be a finite JSON number.")

        if parameter == "seed":
            return self._reject("Seed is managed by Ax3l and cannot be proposed.")
        if parameter not in SINGLE_PARAMETERS:
            return self._reject(f"Parameter is not in the single-parameter search space: {parameter}.")
        path, definition = SINGLE_PARAMETERS[parameter]
        try:
            Draft202012Validator(definition).validate(value)
        except ValidationError as error:
            return self._reject(f"{parameter}: {error.message}")
        if definition["type"] == "integer":
            value = int(value)

        return self._submit_changes([(path, value)], f"{parameter}: {value}")

    def _submit_changes(self, changes: list, description: str) -> dict:
        """Apply validated values together and submit one unique configuration."""
        golden = EventLogDb(self._db).current_golden_config()
        if golden is None:
            raise RuntimeError("No golden configuration has been created")
        baseline = self._snake.get_config(golden["process_id"])
        if baseline is None:
            raise RuntimeError("The golden configuration's run was not found")
        candidate = deepcopy(baseline)
        for path, value in changes:
            node = candidate
            for key in path[:-1]:
                node = node[key]
            node[path[-1]] = value
        # A broken stored baseline is a server/data error, not a bad proposal.
        Draft202012Validator(self._schema).validate(candidate)
        if candidate == baseline:
            return self._reject("The proposed configuration is identical to the golden configuration.", duplicate=True)
        if not self._snake.is_config_unique(candidate):
            return self._reject("The proposed configuration already exists in the simulation database.", duplicate=True)

        run_id = self._snake.submit_simulation(candidate)
        category = DEventCategory.Configuration
        accepted_id = self._db.log(category.PROPOSAL_ACCEPTED, category.CATEGORY, "INFO",
                                   description, process_id=run_id)
        category = DEventCategory.SnakeLab
        self._db.log(category.SUBMITTED, category.CATEGORY, "INFO", "Submitted config.",
                     process_id=run_id, parent_event_id=accepted_id, ax3l_version=DAx3l.VERSION)
        return {"status": "ok", "run_id": run_id}
