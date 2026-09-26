"""Create the series, season, episode and file hierarchy."""

from r3el.interface.DbMgr import DbMgr


class TVSchema:
    def __init__(self, db: DbMgr):
        self.db = db

    def apply(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_series (
            tmdb_id INT UNSIGNED PRIMARY KEY, title TEXT NOT NULL, original_title TEXT NULL,
            first_air_date DATE NULL, overview TEXT NULL, rating DECIMAL(8,5) NULL,
            vote_count INT UNSIGNED NULL, added_at DATETIME(6) NOT NULL,
            fetched_at DATETIME(6) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_seasons (
            series_id INT UNSIGNED NOT NULL, season_number SMALLINT UNSIGNED NOT NULL,
            tmdb_id INT UNSIGNED NOT NULL, title TEXT NOT NULL, overview TEXT NULL, air_date DATE NULL,
            PRIMARY KEY(series_id, season_number),
            FOREIGN KEY(series_id) REFERENCES tv_series(tmdb_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_episodes (
            tmdb_id INT UNSIGNED PRIMARY KEY, series_id INT UNSIGNED NOT NULL,
            season_number SMALLINT UNSIGNED NOT NULL, episode_number SMALLINT UNSIGNED NOT NULL,
            title TEXT NOT NULL, overview TEXT NULL, air_date DATE NULL, runtime INT UNSIGNED NULL,
            UNIQUE(series_id, season_number, episode_number),
            FOREIGN KEY(series_id, season_number) REFERENCES tv_seasons(series_id, season_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_episode_files (
            path_hash BINARY(32) PRIMARY KEY, path TEXT NOT NULL, episode_id INT UNSIGNED NOT NULL,
            kind ENUM('video','subtitle') NOT NULL,
            FOREIGN KEY(episode_id) REFERENCES tv_episodes(tmdb_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_artwork (
            path_hash BINARY(32) PRIMARY KEY, path TEXT NOT NULL, series_id INT UNSIGNED NOT NULL,
            season_number SMALLINT UNSIGNED NULL, episode_id INT UNSIGNED NULL,
            kind ENUM('poster','backdrop','still') NOT NULL,
            FOREIGN KEY(series_id) REFERENCES tv_series(tmdb_id),
            FOREIGN KEY(series_id, season_number) REFERENCES tv_seasons(series_id, season_number),
            FOREIGN KEY(episode_id) REFERENCES tv_episodes(tmdb_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tmdb_tv_genres (
            genre_id INT UNSIGNED PRIMARY KEY, name VARCHAR(100) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS tv_series_genres (
            series_id INT UNSIGNED NOT NULL, genre_id INT UNSIGNED NOT NULL,
            PRIMARY KEY(series_id, genre_id),
            FOREIGN KEY(series_id) REFERENCES tv_series(tmdb_id),
            FOREIGN KEY(genre_id) REFERENCES tmdb_tv_genres(genre_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
        for table, column, parent in (('tv_series_credits', 'series_id', 'tv_series'),
                                       ('tv_episode_credits', 'episode_id', 'tv_episodes')):
            self.db.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
                {column} INT UNSIGNED NOT NULL, position INT UNSIGNED NOT NULL,
                person_id INT UNSIGNED NOT NULL, role_id TINYINT UNSIGNED NOT NULL,
                character_name TEXT NULL, billing_order INT UNSIGNED NULL,
                PRIMARY KEY({column}, position),
                FOREIGN KEY({column}) REFERENCES {parent}(tmdb_id),
                FOREIGN KEY(person_id) REFERENCES people(tmdb_id),
                FOREIGN KEY(role_id) REFERENCES credit_roles(role_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
