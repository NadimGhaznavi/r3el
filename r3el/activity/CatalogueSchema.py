"""Create the normalized catalogue during explicit installation or upgrade."""

from r3el.activity.TMDBReferenceSchema import TMDBReferenceSchema
from r3el.interface.DbMgr import DbMgr


class CatalogueSchema:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def apply(self) -> None:
        TMDBReferenceSchema(self._db).apply()
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS movies (
                tmdb_id INT UNSIGNED PRIMARY KEY,
                title TEXT NOT NULL,
                original_title TEXT NULL,
                release_date DATE NULL,
                release_year SMALLINT UNSIGNED AS (YEAR(release_date)) VIRTUAL,
                overview TEXT NULL,
                runtime INT UNSIGNED NULL,
                poster_path TEXT NULL,
                backdrop_path TEXT NULL,
                imdb_id VARCHAR(32) NULL,
                rating DECIMAL(8,5) NULL,
                vote_count INT UNSIGNED NULL,
                fetched_at DATETIME(6) NOT NULL,
                CHECK (rating BETWEEN 0 AND 10)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('ALTER TABLE movies ADD COLUMN IF NOT EXISTS added_at DATETIME(6) NULL')
        self._db.execute('UPDATE movies SET added_at = fetched_at WHERE added_at IS NULL')
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS people (
                tmdb_id INT UNSIGNED PRIMARY KEY,
                name TEXT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS credit_roles (
                role_id TINYINT UNSIGNED PRIMARY KEY,
                name VARCHAR(32) NOT NULL UNIQUE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        for role_id, name in enumerate(('Actor', 'Director', 'Producer', 'Executive Producer', 'Co-Producer'), 1):
            self._db.execute('INSERT INTO credit_roles (role_id, name) VALUES (%s, %s) '
                             'ON DUPLICATE KEY UPDATE name = VALUES(name)', (role_id, name))
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS movie_credits (
                movie_id INT UNSIGNED NOT NULL,
                position INT UNSIGNED NOT NULL,
                person_id INT UNSIGNED NOT NULL,
                role_id TINYINT UNSIGNED NOT NULL,
                character_name TEXT NULL,
                billing_order INT UNSIGNED NULL,
                PRIMARY KEY (movie_id, position),
                FOREIGN KEY (movie_id) REFERENCES movies(tmdb_id) ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES people(tmdb_id),
                FOREIGN KEY (role_id) REFERENCES credit_roles(role_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS movie_genres (
                movie_id INT UNSIGNED NOT NULL,
                genre_id INT UNSIGNED NOT NULL,
                PRIMARY KEY (movie_id, genre_id),
                FOREIGN KEY (movie_id) REFERENCES movies(tmdb_id) ON DELETE CASCADE,
                FOREIGN KEY (genre_id) REFERENCES tmdb_movie_genres(genre_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS movie_files (
                path_hash BINARY(32) PRIMARY KEY,
                path TEXT NOT NULL,
                movie_id INT UNSIGNED NOT NULL,
                FOREIGN KEY (movie_id) REFERENCES movies(tmdb_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        self._db.execute('ALTER TABLE movie_files ADD COLUMN IF NOT EXISTS part TINYINT UNSIGNED NULL')
        self._db.execute("ALTER TABLE movie_files ADD COLUMN IF NOT EXISTS kind ENUM('video', 'subtitle') NOT NULL DEFAULT 'video'")
        self._db.execute('''
            CREATE TABLE IF NOT EXISTS movie_artwork (
                path_hash BINARY(32) PRIMARY KEY,
                path TEXT NOT NULL,
                movie_id INT UNSIGNED NOT NULL,
                kind ENUM('poster', 'backdrop') NOT NULL,
                FOREIGN KEY (movie_id) REFERENCES movies(tmdb_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')


if __name__ == '__main__':
    db = DbMgr()
    try:
        CatalogueSchema(db).apply()
    finally:
        db.close()
