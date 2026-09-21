"""Persist and query application events through the shared database bridge."""

from r3el.entity.LogEvent import LogEvent
from r3el.interface.DbMgr import DbMgr


class EventLogDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def record(self, event: LogEvent) -> int:
        """Save metadata and message atomically; call outside a transaction."""
        with self._db.transaction():
            return self.record_in_transaction(event)

    def record_in_transaction(self, event: LogEvent) -> int:
        """Append an event inside a transaction owned by the caller."""
        event_id = self._db.insert(
            """INSERT INTO events
            (category, subcategory, name, log_level, process_id,
             parent_event_id, source_name, app_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (event.classification.category, event.classification.subcategory,
             event.name, event.level, event.process_id, event.parent_event_id,
             event.source_name, event.app_version),
        )
        self._db.execute(
            "INSERT INTO event_messages (event_id, content) VALUES (%s, %s)",
            (event_id, event.message),
        )
        return event_id

    def recent(self, *, category: str | None = None,
               subcategory: str | None = None, name: str | None = None,
               limit: int = 500) -> list[dict]:
        """Filter the full history before selecting the newest records."""
        conditions, values = [], []
        if category is not None:
            conditions.append("e.category = %s")
            values.append(category)
        if subcategory is not None:
            conditions.append("e.subcategory = %s")
            values.append(subcategory)
        if name is not None:
            conditions.append("e.name = %s")
            values.append(name)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return self._db.query(
            "SELECT e.*, m.content FROM events e "
            "JOIN event_messages m USING (event_id)" + where +
            " ORDER BY e.occurred_at DESC, e.event_id DESC LIMIT %s",
            tuple(values) + (limit,),
        )

    def get(self, event_id: int) -> dict | None:
        rows = self._db.query(
            "SELECT e.*, m.content FROM events e "
            "JOIN event_messages m USING (event_id) WHERE e.event_id = %s",
            (event_id,),
        )
        return rows[0] if rows else None
