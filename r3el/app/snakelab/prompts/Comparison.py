"""Present the assigned parameter's baseline and comparable history."""

import json

from ax3l.app.DynamicPrompt import DynamicPrompt
from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS
from ax3l.interface.SnakeLab import SnakeLab


class Comparison(DynamicPrompt):
    def __init__(self, current_golden_run_id: str, parameter: str):
        self._current_golden_run_id = current_golden_run_id
        self._parameter = parameter
        self._snake = SnakeLab()
        super().__init__()

    def refresh(self) -> None:
        name = self._parameter
        baseline = self._snake.get_run_result(self._current_golden_run_id)
        value = baseline["config"]
        for key in SINGLE_PARAMETERS[name][0]:
            value = value[key]
        history = self._snake.get_parameter_report(self._current_golden_run_id, name)
        self._content = (
            f"Current golden: {name}={value}, high_score={baseline['high_score']}.\n"
            "Comparable runs (other settings unchanged): results = current seed; "
            "history = earlier-seed high scores. Empty results = untested on this seed.\n"
            f"```json\n{json.dumps(history, ensure_ascii=False, allow_nan=False)}\n```"
        )
