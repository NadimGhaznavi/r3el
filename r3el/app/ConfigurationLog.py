"""Record configuration decisions in the shared event log."""

from ax3l.app.DbMgr import DbMgr
from ax3l.constants.DEventCategory import DEventCategory


class ConfigurationLog:
    def __init__(self, db: DbMgr):
        self._db = db

    def golden_config_created(
        self,
        run_id: str,
        *,
        reason: str,
        parent_event_id: int | None = None,
        experiment_score: dict | None = None,
    ) -> int:
        """Record creation with its comparison or initial-seeding reason."""
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Golden configuration creation requires a reason")
        category = DEventCategory.Configuration
        return self._db.log(
            category.GOLDEN_CREATED, category.CATEGORY, "INFO", reason,
            process_id=run_id, parent_event_id=parent_event_id,
            **({"experiment_score": experiment_score} if experiment_score is not None else {}),
        )
