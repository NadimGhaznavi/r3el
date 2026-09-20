"""MariaDB connection, query, and transaction mechanics."""

from contextlib import contextmanager
import os

import pymysql
from pymysql.cursors import DictCursor

from r3el.constants.DDbMgr import DDbMgr


class DbMgr:
    def __init__(self) -> None:
        self._connection = pymysql.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", DDbMgr.PORT)),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            charset="utf8mb4", cursorclass=DictCursor, autocommit=True,
            connect_timeout=10, read_timeout=30, write_timeout=30,
            init_command="SET time_zone = '+00:00'",
        )

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self._connection.cursor() as cursor:
            return cursor.execute(sql, params)

    def insert(self, sql: str, params: tuple) -> int:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.lastrowid

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())

    @contextmanager
    def transaction(self):
        """Transactions must not be nested; execute DDL separately."""
        self._connection.begin()
        try:
            yield
            self._connection.commit()
        except BaseException:
            self._connection.rollback()
            raise

    def close(self) -> None:
        self._connection.close()
