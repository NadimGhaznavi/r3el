"""Create the durable workspace explicitly during installation and upgrade."""

from r3el.interface.DbMgr import DbMgr
from r3el.constants.DR3el import DR3el
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.MediaFile import MediaFileState


class WorkspaceSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS media_file_batches (
                batch_id CHAR(36) PRIMARY KEY,
                workspace_slot TINYINT NOT NULL DEFAULT 1 UNIQUE CHECK (workspace_slot = 1),
                requested_size INT UNSIGNED NOT NULL CHECK (requested_size > 0),
                source_directory TEXT NOT NULL,
                destination_directory TEXT NULL,
                state ENUM('processing', 'failed', 'cancelled', 'identification_completed') NOT NULL,
                started_event_id BIGINT UNSIGNED NOT NULL,
                FOREIGN KEY (started_event_id) REFERENCES events(event_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        self._db.execute(
            'ALTER TABLE media_file_batches ADD COLUMN IF NOT EXISTS destination_directory TEXT NULL'
        )
        self._db.execute('ALTER TABLE media_file_batches ADD COLUMN IF NOT EXISTS '
                         'stop_requested BOOLEAN NOT NULL DEFAULT FALSE')
        self._db.execute("""
            ALTER TABLE media_file_batches MODIFY COLUMN state
            ENUM('processing', 'failed', 'cancelled', 'identification_completed',
                 'matching', 'matching_completed', 'matching_failed') NOT NULL
        """)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                file_id CHAR(36) PRIMARY KEY,
                batch_id CHAR(36) NOT NULL,
                position INT UNSIGNED NOT NULL,
                path TEXT NOT NULL,
                state ENUM('pending', 'identified', 'unresolved_llm', 'unresolved_hidden_file') NOT NULL,
                identification JSON NULL,
                issues JSON NOT NULL,
                attempts INT UNSIGNED NOT NULL,
                UNIQUE (batch_id, position),
                FOREIGN KEY (batch_id) REFERENCES media_file_batches(batch_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        self._db.execute('ALTER TABLE media_file_batches ADD COLUMN IF NOT EXISTS '
                         'directories_scanned BOOLEAN NOT NULL DEFAULT FALSE')
        self._db.execute('ALTER TABLE media_files ADD COLUMN IF NOT EXISTS find_ls LONGTEXT NULL')
        self._db.execute('ALTER TABLE media_files ADD COLUMN IF NOT EXISTS source_directory TEXT NULL')
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS media_attachments (
                file_id CHAR(36) NOT NULL,
                position INT UNSIGNED NOT NULL,
                path TEXT NOT NULL,
                kind ENUM('video', 'subtitle') NOT NULL,
                part TINYINT UNSIGNED NULL CHECK (part IN (1, 2)),
                media_path TEXT NULL,
                PRIMARY KEY (file_id, position),
                FOREIGN KEY (file_id) REFERENCES media_files(file_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        self._db.execute("ALTER TABLE media_files ADD COLUMN IF NOT EXISTS media_type "
                         "ENUM('movie','tv') NOT NULL DEFAULT 'movie'")
        self._db.execute('ALTER TABLE media_file_batches ADD COLUMN IF NOT EXISTS tv_destination_directory TEXT NULL')
        self._db.execute('ALTER TABLE media_attachments ADD COLUMN IF NOT EXISTS season_number SMALLINT UNSIGNED NULL')
        self._db.execute('ALTER TABLE media_attachments ADD COLUMN IF NOT EXISTS episode_number SMALLINT UNSIGNED NULL')
        self._db.execute('ALTER TABLE media_attachments ADD COLUMN IF NOT EXISTS import_result JSON NULL')
        # NULL marks only unmigrated rows. Reapplying the upgrade preserves user choices.
        self._db.execute('ALTER TABLE media_files ADD COLUMN IF NOT EXISTS tmdb_match JSON NULL')
        self._db.execute('ALTER TABLE media_files ADD COLUMN IF NOT EXISTS '
                         'updated_at DATETIME(6) NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP(6)')
        self._db.execute('ALTER TABLE media_files ADD COLUMN IF NOT EXISTS retries INT UNSIGNED NOT NULL DEFAULT 0')
        self._db.execute("""
            ALTER TABLE media_files ADD COLUMN IF NOT EXISTS
            action ENUM('pending', 'approve', 'ignore', 'delete') NULL DEFAULT NULL
        """)
        self._db.execute(
            'UPDATE media_files SET action = CASE '
            "WHEN state = %s AND JSON_EXTRACT(identification, '$.confidence') = %s "
            'THEN %s ELSE %s END WHERE action IS NULL',
            (MediaFileState.IDENTIFIED, DR3el.AUTO_APPROVE_CONFIDENCE,
             MediaFileAction.APPROVE, MediaFileAction.PENDING),
        )
        self._db.execute("""
            ALTER TABLE media_files MODIFY COLUMN
            action ENUM('pending', 'approve', 'ignore', 'delete') NOT NULL DEFAULT 'pending'
        """)


if __name__ == '__main__':
    db = DbMgr()
    try:
        WorkspaceSchema(db).apply()
    finally:
        db.close()
