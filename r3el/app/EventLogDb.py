import json
from typing import Any

from ax3l.app.DbMgr import DbMgr
from ax3l.constants.DEventCategory import DEventCategory
from ax3l.constants.DSnakeLab import DSnakeLab


class EventLogDb:
    def __init__(self, db: DbMgr):
        self._db = db

    def recent(self) -> list[dict[str, Any]]:
        """Return the latest 500 events, newest first."""
        rows = self._db.query(f"""
            SELECT e.event_id, e.occurred_at, e.name, e.category,
                   e.log_level, e.process_id, e.source_name, e.parameter, e.ax3l_version, m.content,
                   r.high_score AS simulation_high_score
            FROM events e
            LEFT JOIN event_messages m USING (event_id)
            LEFT JOIN `{DSnakeLab.DATABASE}`.simulation_runs r
                ON r.run_id = e.process_id COLLATE utf8mb4_unicode_ci
                AND e.category = 'SnakeLab' AND e.name = 'simulation_completed'
            ORDER BY e.occurred_at DESC, e.event_id DESC
            LIMIT 500
        """)
        return rows

    def get(self, event_id: int) -> dict[str, Any] | None:
        rows = self._db.query("""
            SELECT e.*, m.content
            FROM events e LEFT JOIN event_messages m USING (event_id)
            WHERE e.event_id = %s
        """, (event_id,))
        return rows[0] if rows else None

    def current_golden_config(self) -> dict[str, Any] | None:
        """Return the latest golden creation's run reference and reason."""
        category = DEventCategory.Configuration
        rows = self._db.query("""
            SELECT e.process_id, m.content AS reason
            FROM events e JOIN event_messages m USING (event_id)
            WHERE e.category = %s AND e.name = %s
            ORDER BY e.occurred_at DESC, e.event_id DESC
            LIMIT 1
        """, (category.CATEGORY, category.GOLDEN_CREATED))
        return rows[0] if rows else None

    def golden_configurations(self) -> list[dict[str, Any]]:
        """Include every baseline/promotion and the response that proposed its run."""
        return self._db.query("""
            WITH successful_tools AS (
                SELECT e.event_id, e.process_id,
                       JSON_UNQUOTE(JSON_EXTRACT(CASE WHEN JSON_VALID(m.content) THEN m.content ELSE '{}' END,
                                                 '$.run_id')) AS run_id
                FROM events e JOIN event_messages m USING (event_id)
                WHERE e.category = 'Tool' AND e.name = 'tool_execution_completed'
                  AND JSON_UNQUOTE(JSON_EXTRACT(CASE WHEN JSON_VALID(m.content) THEN m.content ELSE '{}' END,
                                               '$.status')) = 'ok'
            )
            SELECT g.event_id, g.occurred_at, g.process_id, p.parameter, h.score AS high_score,
                   r.event_id AS reply_id, rm.content AS response, gm.content AS decision
            FROM events g
            LEFT JOIN event_messages gm ON gm.event_id = g.event_id
            LEFT JOIN experiment_highscores h ON h.event_id = g.event_id
            LEFT JOIN successful_tools t ON t.event_id = (
                SELECT MIN(event_id) FROM successful_tools WHERE run_id = g.process_id)
            LEFT JOIN events r ON r.event_id = (
                SELECT MAX(event_id) FROM events
                WHERE process_id = t.process_id AND event_id < t.event_id
                  AND category = 'Conversation' AND name = 'reply_received')
            LEFT JOIN event_messages rm ON rm.event_id = r.event_id
            LEFT JOIN events p ON p.event_id = (
                SELECT MAX(event_id) FROM events
                WHERE process_id = r.process_id AND event_id < r.event_id
                  AND category = 'Conversation' AND name = 'prompt_sent')
            WHERE g.category = %s AND g.name = %s
            ORDER BY g.occurred_at DESC, g.event_id DESC
        """, (DEventCategory.Configuration.CATEGORY, DEventCategory.Configuration.GOLDEN_CREATED))

    def latest_snakelab_proposal(self) -> dict[str, Any] | None:
        """Recover the latest accepted run and its recorded comparison, if any."""
        category = DEventCategory.Configuration
        rows = self._db.query("""
            SELECT p.process_id, c.event_id AS comparison_id, m.content AS comparison
            FROM events p
            LEFT JOIN events c ON c.event_id = (
                SELECT MAX(event_id) FROM events
                WHERE process_id = p.process_id AND category = %s AND name = %s
            )
            LEFT JOIN event_messages m ON m.event_id = c.event_id
            WHERE p.category = %s AND p.name = %s
              AND p.event_id > COALESCE((SELECT MAX(event_id) FROM events
                  WHERE category = %s AND name = %s), 0)
            ORDER BY p.event_id DESC LIMIT 1
        """, (category.CATEGORY, category.COMPARED, category.CATEGORY, category.PROPOSAL_ACCEPTED,
               category.CATEGORY, category.GOLDEN_SEED_INCREMENTED))
        return rows[0] if rows else None

    def stagnant_rounds(self) -> int:
        """Count complete ordered passes since the last golden creation.

        An improvement in the middle of a pass discards that partial pass.
        Count comparisons and exhausted steps, not acceptances, so pending runs
        and retries cannot trigger rotation. Durable events survive restarts.
        """
        return self._completed_rounds(since_golden=True)

    def experiment_cycles(self) -> int:
        """Count completed round robins across all golden configs and seeds."""
        return self._completed_rounds(since_golden=False)

    def _completed_rounds(self, *, since_golden: bool) -> int:
        from ax3l.app.snakelab.RoundRobinState import ROUND_ROBIN_ORDER

        category = DEventCategory.Configuration
        rows = self._db.query("""
            SELECT c.event_id AS completion_id, c.process_id, m.content
            FROM events c
            JOIN events p ON p.event_id = (
                SELECT MIN(event_id) FROM events
                WHERE process_id = c.process_id AND category = %s AND name = %s)
            JOIN events checkpoint ON checkpoint.event_id = (
                SELECT MAX(event_id) FROM events
                WHERE event_id < p.event_id AND category = %s AND name = %s)
            JOIN event_messages m ON m.event_id = checkpoint.event_id
            WHERE c.category = %s AND c.name = %s AND (%s = 0 OR c.event_id > COALESCE(
                (SELECT MAX(event_id) FROM events WHERE category = %s AND name = %s), 0))
            UNION ALL
            SELECT c.event_id AS completion_id, NULL AS process_id, m.content
            FROM events c
            JOIN events checkpoint ON checkpoint.event_id = (
                SELECT MAX(event_id) FROM events
                WHERE event_id < c.event_id AND category = %s AND name = %s)
            JOIN event_messages m ON m.event_id = checkpoint.event_id
            WHERE c.category = %s AND c.name = %s AND (%s = 0 OR c.event_id > COALESCE(
                (SELECT MAX(event_id) FROM events WHERE category = %s AND name = %s), 0))
            ORDER BY completion_id
        """, (category.CATEGORY, category.PROPOSAL_ACCEPTED,
               category.CATEGORY, "round_robin_checkpoint",
               category.CATEGORY, category.COMPARED, int(since_golden),
               category.CATEGORY, category.GOLDEN_CREATED,
               category.CATEGORY, "round_robin_checkpoint",
               category.CATEGORY, category.PARAMETER_SPACE_EXHAUSTED, int(since_golden),
               category.CATEGORY, category.GOLDEN_CREATED))
        order = ROUND_ROBIN_ORDER
        rounds, expected = 0, 0
        seen = set()
        for row in rows:
            identity = row["process_id"] if row["process_id"] is not None else row["completion_id"]
            if identity in seen:
                continue
            seen.add(identity)
            checkpoint = json.loads(row["content"])
            if checkpoint["parameter_order"] != order:
                raise ValueError("Search parameter order changed; reset experiment events before resuming")
            index = checkpoint["index"]
            if index != expected:
                expected = 0
                if index != 0:
                    continue
            expected += 1
            if expected == len(order):
                rounds += 1
                expected = 0
        return rounds

    def pending_seed_rotation(self) -> dict[str, Any] | None:
        category = DEventCategory.Configuration
        rows = self._db.query("""
            SELECT i.event_id, i.ax3l_version, m.content, s.event_id AS submitted_event_id, s.process_id AS run_id
            FROM events i JOIN event_messages m ON m.event_id = i.event_id
            LEFT JOIN events s ON s.parent_event_id = i.event_id AND s.name = %s AND s.category = %s
            WHERE i.name = %s AND i.category = %s
              AND NOT EXISTS (SELECT 1 FROM events g WHERE g.parent_event_id = s.event_id
                              AND g.name = %s AND g.category = %s)
            ORDER BY i.event_id DESC LIMIT 1
        """, (category.GOLDEN_SEED_INCREMENTED, category.CATEGORY,
               category.SEED_ROTATION_STARTED, category.CATEGORY,
               category.GOLDEN_CREATED, category.CATEGORY))
        return rows[0] if rows else None

    def latest_seed_baseline(self) -> str | None:
        category = DEventCategory.Configuration
        rows = self._db.query("""
            SELECT g.process_id FROM events g JOIN events s ON g.parent_event_id = s.event_id
            WHERE g.name = %s AND g.category = %s AND s.name = %s AND s.category = %s
            ORDER BY g.event_id DESC LIMIT 1
        """, (category.GOLDEN_CREATED, category.CATEGORY,
               category.GOLDEN_SEED_INCREMENTED, category.CATEGORY))
        return rows[0]["process_id"] if rows else None

    def experiment_highscores(self) -> list[dict[str, Any]]:
        """Read accepted scores in decision order, including lower seed baselines."""
        return self._db.query("""
            SELECT h.simulations, h.score, h.seed, e.process_id AS run_id, m.content AS reason
            FROM experiment_highscores h JOIN events e USING (event_id)
            JOIN event_messages m USING (event_id)
            ORDER BY h.event_id
        """)
