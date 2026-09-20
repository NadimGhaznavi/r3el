"""MariaDB access and initialization of the shared event logging tables."""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import os
from typing import Any

import pymysql
from pymysql.cursors import DictCursor

from ax3l.constants.DDbMgr import DDbMgr


class DbMgr:
    def __init__(self, *, database: str | None = None, initialize_event_tables: bool = True):
        self._connection = pymysql.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", DDbMgr.PORT)),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=database if database is not None else os.environ["DB_NAME"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=True,
        )
        try:
            if initialize_event_tables:
                self._initialize_event_tables()
        except Exception:
            self.close()
            raise

    def _initialize_event_tables(self) -> None:
        statements = (
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
                name VARCHAR(100) NOT NULL,
                category VARCHAR(50) NOT NULL,
                log_level VARCHAR(10) NOT NULL,
                process_id CHAR(36) NULL,
                parent_event_id BIGINT UNSIGNED NULL,
                source_name VARCHAR(255) NULL,
                parameter VARCHAR(100) NULL,
                ax3l_version VARCHAR(100) NULL,
                INDEX idx_event_time (occurred_at, event_id),
                INDEX idx_event_name_time (name, occurred_at),
                INDEX idx_event_process (process_id, event_id),
                FOREIGN KEY (parent_event_id) REFERENCES events(event_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS event_messages (
                event_id BIGINT UNSIGNED PRIMARY KEY,
                content LONGTEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(event_id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS event_list_items (
                event_id BIGINT UNSIGNED NOT NULL,
                position INT UNSIGNED NOT NULL,
                value LONGTEXT NOT NULL,
                PRIMARY KEY (event_id, position),
                FOREIGN KEY (event_id) REFERENCES events(event_id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
            """
            CREATE TABLE IF NOT EXISTS event_key_values (
                event_id BIGINT UNSIGNED NOT NULL,
                entry_key VARCHAR(100) COLLATE utf8mb4_bin NOT NULL,
                value LONGTEXT NOT NULL,
                PRIMARY KEY (event_id, entry_key),
                FOREIGN KEY (event_id) REFERENCES events(event_id)
                    ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        )
        statements += ("""
            CREATE TABLE IF NOT EXISTS experiment_highscores (
                event_id BIGINT UNSIGNED PRIMARY KEY,
                simulations BIGINT UNSIGNED NOT NULL,
                score INT NOT NULL,
                seed BIGINT NULL,
                FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """,)
        for statement in statements:
            self.execute(statement)

    def log(
        self,
        name: str,
        category: str,
        log_level: str,
        content: str,
        *,
        process_id: str | None = None,
        parent_event_id: int | None = None,
        source_name: str | None = None,
        parameter: str | None = None,
        ax3l_version: str | None = None,
        experiment_score: dict | None = None,
    ) -> int:
        """Commit an event and its message together and return the event ID.

        This method owns its transaction; call it outside transaction().
        """
        with self.transaction():
            self.execute(
                """INSERT INTO events
                   (name, category, log_level, process_id, parent_event_id, source_name, parameter, ax3l_version)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (name, category, log_level, process_id, parent_event_id, source_name, parameter, ax3l_version),
            )
            event_id = self.query("SELECT LAST_INSERT_ID() AS event_id")[0]["event_id"]
            self.execute(
                "INSERT INTO event_messages (event_id, content) VALUES (%s, %s)",
                (event_id, content),
            )
            if experiment_score is not None:
                self.execute(
                    "INSERT INTO experiment_highscores (event_id, simulations, score, seed) VALUES (%s, %s, %s, %s)",
                    (event_id, experiment_score["simulations"], experiment_score["score"], experiment_score["seed"]),
                )
        return event_id

    def execute(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> int:
        """Execute parameterized SQL and return the affected row count."""
        with self._connection.cursor() as cursor:
            return cursor.execute(sql, params)

    def query(
        self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute parameterized SQL and return rows by column name."""
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Commit a group of writes together, or roll them back on failure.

        Transactions must not be nested. MariaDB DDL implicitly commits and
        must be kept outside these application write transactions.
        """
        self._connection.begin()
        try:
            yield
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise

    def close(self) -> None:
        self._connection.close()
