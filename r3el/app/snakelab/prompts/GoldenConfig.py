"""Present the current golden configuration as a refreshable LLM snippet."""

import json

from ax3l.app.DbMgr import DbMgr
from ax3l.app.DynamicPrompt import DynamicPrompt
from ax3l.app.EventLogDb import EventLogDb
from ax3l.interface.SnakeLab import SnakeLab


class GoldenConfig(DynamicPrompt):
    """Use GoldenConfig(db), then refresh() before reusing it in a conversation.

    The caller owns the AX3L database connection. Rendering uses the snapshot
    loaded by construction or the most recent successful refresh.
    """

    def __init__(self, db: DbMgr):
        self._events = EventLogDb(db)
        self._snake_lab = SnakeLab()
        super().__init__()

    def refresh(self) -> None:
        golden = self._events.current_golden_config()
        if golden is None:
            raise ValueError("No golden configuration has been created")
        config = self._snake_lab.get_config(golden["process_id"])
        if config is None:
            raise ValueError(f"Golden configuration run {golden['process_id']} was not found")
        config = {key: value for key, value in config.items() if key != "seed"}
        self._content = (
            "Current Golden Configuration\n\n"
            f"Reason: {golden['reason']}\n\n"
            "```json\n"
            f"{json.dumps(config, indent=2, ensure_ascii=False, allow_nan=False)}\n"
            "```"
        )
        self.run_id = golden["process_id"]
