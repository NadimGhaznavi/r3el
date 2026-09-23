"""Create shared TMDB reference tables during explicit setup."""

from r3el.interface.DbMgr import DbMgr


class TMDBReferenceSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS tmdb_movie_genres (
                genre_id INT UNSIGNED PRIMARY KEY,
                name VARCHAR(100) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS tmdb_languages (
                language_code CHAR(2) COLLATE utf8mb4_bin PRIMARY KEY,
                english_name VARCHAR(100) NOT NULL,
                native_name VARCHAR(100) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
