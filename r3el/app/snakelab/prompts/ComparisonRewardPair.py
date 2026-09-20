"""Present the golden distance rewards and a complete comparable-score grid."""

import json

from ax3l.app.DynamicPrompt import DynamicPrompt
from ax3l.interface.SnakeLab import SnakeLab


class ComparisonRewardPair(DynamicPrompt):
    def __init__(self, current_golden_run_id: str):
        self._current_golden_run_id = current_golden_run_id
        self._snake = SnakeLab()
        super().__init__()

    def refresh(self) -> None:
        baseline = self._snake.get_run_result(self._current_golden_run_id)
        rewards = baseline["config"]["game"]["rewards"]
        report = {
            "gold": {
                "closer_to_food": rewards["closer_to_food"],
                "further_from_food": rewards["further_from_food"],
                "high_score": baseline["high_score"],
            },
            "results": self._snake.get_reward_report(self._current_golden_run_id),
        }
        self._content = (
            f"```json\n{json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2)}\n```\n"
            "\nrows = closer_to_food: 0..6\n"
            "columns = further_from_food: -6..0\n\n"
            "Results rows are closer_to_food; columns are further_from_food. "
            "Both axes and scores are sorted ascending. Each cell contains "
            "completed-run high scores across all seeds, with all other settings "
            "unchanged from gold. Empty cells mean no completed scored runs for "
            "that combination; it may be untested, unfinished, or failed."
        )
