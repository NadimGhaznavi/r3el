"""Run from the checkout: python3 -m ax3l.app.snakelab.main-loop --url URL."""

import argparse
import os
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import time
import traceback

from ax3l.app.snakelab.SnakeLabLoop import run_optimization
from ax3l.app.DbMgr import DbMgr
from ax3l.app.EventLogDb import EventLogDb
from ax3l.app.ConfigurationLog import ConfigurationLog
from ax3l.app.snakelab.GenerateDefaultConfig import GenerateDefaultConfig
from ax3l.constants.DEventCategory import DEventCategory

from ax3l.constants.DSnakeLab import DSnakeLab
from ax3l.constants.DAx3l import DAx3l
from ax3l.interface.LLM import LLM
from ax3l.interface.SnakeLab import SnakeLab


def initialize_simulation(db: DbMgr) -> None:
    """Submit the first simulation and wait for its cycle to finish."""
    snake = SnakeLab()
    if snake.get_num_sims() != 0:
        if EventLogDb(db).current_golden_config() is not None:
            return
        # Finish the initial baseline after a restart before its acceptance.
        rows = db.query("""
            SELECT event_id, process_id FROM events
            WHERE category = %s AND name = %s ORDER BY event_id LIMIT 1
        """, (DEventCategory.SnakeLab.CATEGORY, DEventCategory.SnakeLab.SUBMITTED))
        if not rows:
            raise RuntimeError("Stored simulations have no initial submission event")
        run_id, submitted_id = rows[0]["process_id"], rows[0]["event_id"]
    else:
        run_id = snake.submit_simulation(GenerateDefaultConfig().run())
        submitted_id = db.log(
            DEventCategory.SnakeLab.SUBMITTED, DEventCategory.SnakeLab.CATEGORY, "INFO", "Submitted config.",
            process_id=run_id, ax3l_version=DAx3l.VERSION,
        )
    started = False
    while True:
        time.sleep(DSnakeLab.STATUS_POLL_SECONDS)
        state = snake.get_simulation_status(run_id)
        if state == "running" and not started:
            db.log(
                DEventCategory.SnakeLab.STARTED, DEventCategory.SnakeLab.CATEGORY, "INFO", "Simulation started running.",
                process_id=run_id, parent_event_id=submitted_id,
            )
            started = True
        if state in ("completed", "failed", "cancelled"):
            db.log(
                DEventCategory.SnakeLab.TERMINAL_EVENTS[state], DEventCategory.SnakeLab.CATEGORY, "ERROR" if state == "failed" else "INFO",
                f"Simulation {state}." if started else
                f"Simulation {state} before running status was observed.",
                process_id=run_id, parent_event_id=submitted_id,
            )
            if state == "completed":
                result = snake.get_run_result(run_id)
                if result is None or result["high_score"] is None:
                    raise ValueError("Initial baseline requires a recorded high score")
                ConfigurationLog(db).golden_config_created(
                    run_id, reason="Seeded database with default config.", parent_event_id=submitted_id,
                    experiment_score={"simulations": snake.get_num_sims(), "score": result["high_score"],
                                      "seed": result["config"]["seed"]},
                )
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Snake Lab single-parameter optimization loop.")
    parser.add_argument("--url", required=True, help="LLM server base URL, e.g. http://host:27770")
    parser.add_argument("--output", type=Path, default=Path("tmp/snakelab"))
    parser.add_argument("--zmq-endpoint", default=os.environ.get("AX3L_ZMQ_ENDPOINT", DAx3l.ZMQ_ENDPOINT))
    args = parser.parse_args(argv)
    output = args.output
    with ExitStack() as captures:
        if DAx3l.RAW_LOGS_ENABLED:
            output = output / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            output.mkdir(parents=True)
            print(f"Capturing output in {output.resolve()}", flush=True)
            log = captures.enter_context((output / "run.log").open("w", encoding="utf-8", buffering=1))
            captures.enter_context(redirect_stdout(log))
            captures.enter_context(redirect_stderr(log))
        try:
            db = DbMgr()
            try:
                initialize_simulation(db)
                run_optimization(LLM(args.url), output, db, args.zmq_endpoint)
            finally:
                db.close()
        except KeyboardInterrupt:
            print("Stopped by user.")
            return 130
        except Exception:
            traceback.print_exc()
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
