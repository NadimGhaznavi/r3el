"""Alternate MCP submissions, completed simulations, and fresh comparisons."""

import asyncio
import json

from ax3l.app.ConfigurationLog import ConfigurationLog
from ax3l.app.EventLogDb import EventLogDb
from ax3l.app.snakelab.ToolConversation import converse
from ax3l.app.snakelab.SeedRotation import rotate_if_needed
from ax3l.app.snakelab.RoundRobinState import RoundRobinState
from ax3l.app.snakelab.ParameterSpace import finite_choices
from ax3l.app.snakelab.prompts.Comparison import Comparison
from ax3l.app.snakelab.prompts.ComparisonSingle import ComparisonSingle
from ax3l.app.snakelab.prompts.FirstContact import FirstContact
from ax3l.app.snakelab.prompts.ProjectContext import ProjectContext
from ax3l.app.snakelab.prompts.FirstContactSingle import FirstContactSingle
from ax3l.app.snakelab.prompts.FirstContactEpsilonPair import FirstContactEpsilonPair
from ax3l.app.snakelab.prompts.FirstContactRewardPair import FirstContactRewardPair
from ax3l.app.snakelab.prompts.ComparisonEpsilonPair import ComparisonEpsilonPair
from ax3l.app.snakelab.prompts.ComparisonRewardPair import ComparisonRewardPair
from ax3l.app.snakelab.prompts.GoldenConfig import GoldenConfig
from ax3l.constants.DEventCategory import DEventCategory as Events
from ax3l.constants.DSnakeLab import DSnakeLab
from ax3l.interface.SnakeLab import SnakeLab, SimulationUnavailable
from ax3l.interface.SnakeLabTools import SnakeLabTools


class SimulationUnsuccessful(RuntimeError):
    """A simulation ended without completed results to compare."""


async def wait_for_run(snake, db, run_id):
    started = False
    while True:
        try:
            state = snake.get_simulation_status(run_id)
        except SimulationUnavailable as error:
            db.log(Events.SnakeLab.FAILED, Events.SnakeLab.CATEGORY, "ERROR",
                   str(error), process_id=run_id)
            raise
        if state == "running" and not started:
            db.log(Events.SnakeLab.STARTED, Events.SnakeLab.CATEGORY, "INFO",
                   "Simulation started running.", process_id=run_id)
            started = True
        if state in Events.SnakeLab.TERMINAL_EVENTS:
            db.log(Events.SnakeLab.TERMINAL_EVENTS[state], Events.SnakeLab.CATEGORY,
                   "INFO" if state == "completed" else "ERROR", f"Simulation {state}.", process_id=run_id)
            if state != "completed":
                raise SimulationUnsuccessful(f"Simulation {run_id} {state}; cannot compare completed results")
            return
        await asyncio.sleep(DSnakeLab.STATUS_POLL_SECONDS)


def compare(snake, db, golden_id, latest_id):
    golden = snake.get_run_result(golden_id)
    latest = snake.get_run_result(latest_id)
    for result in (golden, latest):
        if result is None or result["status"] != "completed" or result["high_score"] is None:
            raise ValueError("Comparison requires two completed simulations with recorded high scores")
    won = latest["high_score"] > golden["high_score"]
    current_id = latest_id if won else golden_id

    def changes(before, after, path=""):
        for key in before:
            name = f"{path}.{key}" if path else key
            if isinstance(before[key], dict):
                yield from changes(before[key], after[key], name)
            elif before[key] != after[key]:
                yield f"{name}: {before[key]} -> {after[key]}"

    reason = (f"High score: {latest['high_score']} {'>' if won else '<='} {golden['high_score']}; "
              + "; ".join(changes(golden["config"], latest["config"])) + ".")
    comparison_id = db.log(Events.Configuration.COMPARED, Events.Configuration.CATEGORY, "INFO",
                          json.dumps({"golden_run_id": golden_id, "latest_run_id": latest_id,
                                      "current_golden_run_id": current_id, "reason": reason}),
                          process_id=latest_id)
    if won:
        ConfigurationLog(db).golden_config_created(latest_id, reason=reason, parent_event_id=comparison_id,
            experiment_score={"simulations": snake.get_num_sims(), "score": latest["high_score"],
                              "seed": latest["config"].get("seed")})
    else:
        db.log(Events.Configuration.GOLDEN_RETAINED, Events.Configuration.CATEGORY, "INFO", reason,
               process_id=golden_id, parent_event_id=comparison_id)
    return current_id


async def optimize(llm, output, db, endpoint):
    snake = SnakeLab()
    while snake.is_simulation_running():
        await asyncio.sleep(DSnakeLab.STATUS_POLL_SECONDS)
    await rotate_if_needed(snake, db, wait_for_run, resume_only=True)
    golden = GoldenConfig(db)
    golden_id = golden.run_id
    baseline = snake.get_run_result(golden_id)
    if baseline is None or baseline["status"] != "completed" or baseline["high_score"] is None:
        raise ValueError("The initial golden simulation must have completed with a high score")
    proposal = EventLogDb(db).latest_snakelab_proposal()
    if proposal:
        latest_id = proposal["process_id"]
        if proposal["comparison"]:
            snapshot = json.loads(proposal["comparison"])
            selected_id = snapshot["current_golden_run_id"]
            # Finish a promotion interrupted between the comparison and creation events.
            if selected_id != golden_id:
                ConfigurationLog(db).golden_config_created(
                    selected_id, reason=snapshot["reason"], parent_event_id=proposal["comparison_id"],
                    experiment_score={"simulations": snake.get_num_sims(),
                                      "score": snake.get_run_result(selected_id)["high_score"],
                                      "seed": snake.get_config(selected_id).get("seed")})
            golden_id = selected_id
        else:
            try:
                await wait_for_run(snake, db, latest_id)
            except (SimulationUnavailable, SimulationUnsuccessful):
                db.log(Events.Configuration.GOLDEN_RETAINED, Events.Configuration.CATEGORY,
                       "WARNING", f"Skipping interrupted proposal {latest_id}; retaining the golden configuration.",
                       process_id=golden_id)
            else:
                golden_id = compare(snake, db, golden_id, latest_id)
    first_contact = proposal is None and EventLogDb(db).latest_seed_baseline() is None
    selector = RoundRobinState(db)
    while True:
        rotated_id = await rotate_if_needed(snake, db, wait_for_run)
        if rotated_id is not None:
            golden_id = rotated_id
            first_contact = False
        parameter = selector.begin()
        if (finite_choices(parameter) is not None
                and snake.parameter_space_exhausted(golden_id, parameter)):
            selector.skip_exhausted(parameter)
            continue
        if parameter == "epsilon_pair":
            prompts = [ComparisonEpsilonPair(golden_id), FirstContactEpsilonPair()]
        elif parameter == "reward_pair":
            prompts = [ComparisonRewardPair(golden_id), FirstContactRewardPair()]
        else:
            prompts = [Comparison(golden_id, parameter),
                       FirstContactSingle(parameter) if first_contact else ComparisonSingle(parameter)]
        if first_contact:
            prompts.insert(0, FirstContact())
        prompts.insert(0, ProjectContext())
        async with SnakeLabTools(endpoint, parameter) as tools:
            latest_id = await converse(llm, output, db, tools, prompts, parameter=parameter)
        await wait_for_run(snake, db, latest_id)
        while snake.is_simulation_running():
            await asyncio.sleep(DSnakeLab.STATUS_POLL_SECONDS)
        golden_id = compare(snake, db, golden_id, latest_id)
        first_contact = False


def run_optimization(llm, output, db, endpoint):
    asyncio.run(optimize(llm, output, db, endpoint))
