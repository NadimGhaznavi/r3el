"""Explicit event schema setup, invoked during installation and upgrade."""

from r3el.constants.DEventCategory import DEventCategory
from r3el.interface.DbMgr import DbMgr


class EventSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS event_categories (
                category VARCHAR(50) COLLATE utf8mb4_bin NOT NULL,
                subcategory VARCHAR(50) COLLATE utf8mb4_bin NOT NULL,
                PRIMARY KEY (category, subcategory)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # Keep historical pairs so adding or retiring categories preserves logs.
        for item in DEventCategory.ALL:
            self._db.execute("""
                INSERT INTO event_categories (category, subcategory) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE category = VALUES(category)
            """, (item.category, item.subcategory))
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                category VARCHAR(50) COLLATE utf8mb4_bin NOT NULL,
                subcategory VARCHAR(50) COLLATE utf8mb4_bin NOT NULL,
                name VARCHAR(100) NOT NULL,
                log_level VARCHAR(10) NOT NULL,
                process_id CHAR(36) NULL,
                parent_event_id BIGINT UNSIGNED NULL,
                source_name VARCHAR(255) NULL,
                app_version VARCHAR(100) NULL,
                INDEX idx_event_time (occurred_at, event_id),
                INDEX idx_event_category_time (category, occurred_at, event_id),
                INDEX idx_event_classification_time (category, subcategory, occurred_at, event_id),
                INDEX idx_event_process (process_id, event_id),
                FOREIGN KEY (category, subcategory)
                    REFERENCES event_categories(category, subcategory),
                FOREIGN KEY (parent_event_id) REFERENCES events(event_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS event_messages (
                event_id BIGINT UNSIGNED PRIMARY KEY,
                content LONGTEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)


if __name__ == "__main__":
    db = DbMgr()
    try:
        EventSchema(db).apply()
    finally:
        db.close()
