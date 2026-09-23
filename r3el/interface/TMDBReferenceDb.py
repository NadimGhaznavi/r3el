"""Persist and read shared TMDB catalogs through the application's DbMgr."""

from r3el.entity.TMDBReference import TMDBGenre, TMDBLanguage, TMDBReference
from r3el.interface.DbMgr import DbMgr


class TMDBReferenceDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def save(self, reference: TMDBReference) -> None:
        """Refresh names atomically, preserving IDs that future media records may reference."""
        with self._db.transaction():
            for genre in reference.genres:
                self._db.execute(
                    'INSERT INTO tmdb_movie_genres (genre_id, name) VALUES (%s, %s) '
                    'ON DUPLICATE KEY UPDATE name = VALUES(name)', (genre.id, genre.name))
            for language in reference.languages:
                self._db.execute(
                    'INSERT INTO tmdb_languages (language_code, english_name, native_name) '
                    'VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE '
                    'english_name = VALUES(english_name), native_name = VALUES(native_name)',
                    (language.code, language.english_name, language.native_name))

    def load(self) -> TMDBReference:
        with self._db.transaction():
            genres = self._db.query('SELECT genre_id, name FROM tmdb_movie_genres ORDER BY genre_id')
            languages = self._db.query(
                'SELECT language_code, english_name, native_name FROM tmdb_languages ORDER BY language_code')
        return TMDBReference(
            [TMDBGenre(row['genre_id'], row['name']) for row in genres],
            [TMDBLanguage(row['language_code'], row['english_name'], row['native_name']) for row in languages])
