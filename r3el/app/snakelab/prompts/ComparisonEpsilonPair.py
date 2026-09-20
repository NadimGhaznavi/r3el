"""Present the golden epsilon pair and sorted comparable scores."""

import json

from ax3l.app.DynamicPrompt import DynamicPrompt
from ax3l.interface.SnakeLab import SnakeLab


class ComparisonEpsilonPair(DynamicPrompt):
    def __init__(self, current_golden_run_id: str):
        self._current_golden_run_id = current_golden_run_id
        self._snake = SnakeLab()
        super().__init__()

    def refresh(self) -> None:
        baseline = self._snake.get_run_result(self._current_golden_run_id)
        epsilon = baseline["config"]["epsilon"]
        history = self._snake.get_epsilon_report(self._current_golden_run_id)
        self._content = (
            "Current golden epsilon:\n"
            f"initial={epsilon['initial']}, decay={epsilon['decay']}, "
            f"high_score={baseline['high_score']}.\n\n"
            "Comparable results:\n"
            f"```json\n{json.dumps(history, ensure_ascii=False, allow_nan=False, indent=2)}\n```\n"
            "Scores are completed-run high scores across seeds, with all other "
            "settings unchanged. Initial, decay, and scores are sorted ascending. "
            "Empty scores mean no completed scored runs for that combination; "
            "it may be untested, unfinished, or failed."
        )
