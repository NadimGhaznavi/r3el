"""Checkpoint the current parameter in the shared event database."""

import json

from ax3l.app.snakelab.SingleParameters import SINGLE_PARAMETERS
from ax3l.app.snakelab.PairParameters import PAIR_PARAMETERS
from ax3l.constants.DEventCategory import DEventCategory as Events


ROUND_ROBIN_ORDER = list(SINGLE_PARAMETERS) + list(PAIR_PARAMETERS)


class RoundRobinState:
    def __init__(self, db):
        self.db = db
        self.order = list(ROUND_ROBIN_ORDER)

    def begin(self):
        """Resume an unfinished turn, or advance past an acceptance or skip.

        The acceptance event is already durable before MCP replies. Using it as
        the completion marker also handles a lost reply without skipping a turn.
        Refuse to reinterpret checkpoints from a different experiment order.
        """
        rows = self.db.query("""
            SELECT e.event_id, m.content,
                   EXISTS(SELECT 1 FROM events p
                          WHERE p.event_id > e.event_id AND p.category = %s
                            AND p.name IN (%s, 'parameter_space_exhausted')) AS accepted
            FROM events e JOIN event_messages m USING (event_id)
            WHERE e.category = %s AND e.name = %s
            ORDER BY e.event_id DESC LIMIT 1
        """, (Events.Configuration.CATEGORY, Events.Configuration.PROPOSAL_ACCEPTED,
               Events.Configuration.CATEGORY, "round_robin_checkpoint"))
        index = 0
        if rows:
            saved = json.loads(rows[0]["content"])
            if saved["parameter_order"] != self.order:
                raise ValueError("Search parameter order changed; reset experiment events before resuming")
            index = saved["index"]
            if type(index) is not int or not 0 <= index < len(self.order):
                raise ValueError("Invalid round-robin checkpoint index")
            if rows[0]["accepted"]:
                index = (index + 1) % len(self.order)
        self.db.log("round_robin_checkpoint", Events.Configuration.CATEGORY, "INFO",
                    json.dumps({"parameter_order": self.order, "index": index}))
        return self.order[index]

    def skip_exhausted(self, parameter):
        """Durably complete this turn without submitting a duplicate proposal."""
        self.db.log(Events.Configuration.PARAMETER_SPACE_EXHAUSTED, Events.Configuration.CATEGORY, "INFO",
                    f"Skipping {parameter}: all legal choices already exist for the current "
                    "seed and otherwise identical configuration. Advancing to the next round-robin step.",
                    parameter=parameter)
