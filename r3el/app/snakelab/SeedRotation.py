"""Rerun the current golden configuration to establish a fresh score baseline."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator

from ax3l.app.ConfigurationLog import ConfigurationLog
from ax3l.app.EventLogDb import EventLogDb
from ax3l.constants.DEventCategory import DEventCategory as Events
from ax3l.constants.DSnakeLab import DSnakeLab
from ax3l.constants.DAx3l import DAx3l


async def rotate_if_needed(snake, db, wait_for_run, *, resume_only=False) -> str | None:
    events = EventLogDb(db)
    pending = events.pending_seed_rotation()
    fresh = pending is None
    if fresh:
        if resume_only:
            return None
        if events.stagnant_rounds() < DSnakeLab.SEED_STAGNANT_ROUNDS:
            return None
        golden_id = events.current_golden_config()["process_id"]
        config = deepcopy(snake.get_config(golden_id))
        config["seed"] += 1
        schema = json.loads((Path(__file__).parent / "simulation-config-v2.schema.json").read_text())
        Draft202012Validator(schema).validate(config)
        intent_id = db.log(Events.Configuration.SEED_ROTATION_STARTED, Events.Configuration.CATEGORY,
                           "INFO", json.dumps({"config": config, "golden_run_id": golden_id}),
                           process_id=str(uuid4()), ax3l_version=DAx3l.VERSION)
        pending = {"event_id": intent_id, "run_id": None, "submitted_event_id": None,
                   "ax3l_version": DAx3l.VERSION}
    else:
        config = json.loads(pending["content"])["config"]
    run_id = pending["run_id"]
    if run_id is None:
        # Reconcile an interrupted/ambiguous submission by full config, never by retrying it.
        run_id = snake.find_config_run(config)
        if run_id is None:
            if not fresh:
                raise RuntimeError("Seed rotation submission is unresolved; no matching simulation was found")
            run_id = snake.submit_simulation(config)
        pending["submitted_event_id"] = db.log(
            Events.Configuration.GOLDEN_SEED_INCREMENTED, Events.Configuration.CATEGORY, "INFO",
            "Submitted golden configuration with the next seed after stagnant round-robin cycles.",
            process_id=run_id, parent_event_id=pending["event_id"])
        db.log(Events.SnakeLab.SUBMITTED, Events.SnakeLab.CATEGORY, "INFO",
               "Submitted config for a fresh baseline.", process_id=run_id,
               parent_event_id=pending["submitted_event_id"], ax3l_version=pending.get("ax3l_version"))
    await wait_for_run(snake, db, run_id)
    result = snake.get_run_result(run_id)
    if result is None or result["status"] != "completed" or result["high_score"] is None:
        raise ValueError("Seed baseline requires a completed simulation with a recorded high score")
    ConfigurationLog(db).golden_config_created(
        run_id, reason=f"Fresh baseline after seed rotation. Score to beat: {result['high_score']}.",
        parent_event_id=pending["submitted_event_id"],
        experiment_score={"simulations": snake.get_num_sims(), "score": result["high_score"],
                          "seed": config["seed"]})
    return run_id
