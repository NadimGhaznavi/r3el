"""Save normalized movie records through the shared database interface."""

from hashlib import sha256

from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.DbMgr import DbMgr


class CatalogueDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def save_in_transaction(self, movie: CatalogueMovie, files: MovieFiles) -> None:
        """Caller owns the transaction, including any workspace checkpoint."""
        self._db.execute('''
            INSERT INTO movies (tmdb_id, title, original_title, release_date, overview, runtime,
                                poster_path, backdrop_path, imdb_id, rating, vote_count, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(6))
            ON DUPLICATE KEY UPDATE title = VALUES(title), original_title = VALUES(original_title),
                release_date = VALUES(release_date), overview = VALUES(overview), runtime = VALUES(runtime),
                poster_path = VALUES(poster_path), backdrop_path = VALUES(backdrop_path),
                imdb_id = VALUES(imdb_id), rating = VALUES(rating), vote_count = VALUES(vote_count),
                fetched_at = VALUES(fetched_at)
        ''', (movie.tmdb_id, movie.title, movie.original_title, movie.release_date, movie.overview,
              movie.runtime, movie.poster_path, movie.backdrop_path, movie.imdb_id, movie.rating, movie.vote_count))
        # The movie upsert holds its row lock until all related records are refreshed.
        self._db.execute('DELETE FROM movie_genres WHERE movie_id = %s', (movie.tmdb_id,))
        for genre in movie.genres:
            self._db.execute('INSERT INTO tmdb_movie_genres (genre_id, name) VALUES (%s, %s) '
                             'ON DUPLICATE KEY UPDATE name = VALUES(name)', (genre.id, genre.name))
            self._db.execute('INSERT INTO movie_genres (movie_id, genre_id) VALUES (%s, %s)',
                             (movie.tmdb_id, genre.id))
        roles = {row['name']: row['role_id'] for row in self._db.query('SELECT role_id, name FROM credit_roles')}
        self._db.execute('DELETE FROM movie_credits WHERE movie_id = %s', (movie.tmdb_id,))
        for position, credit in enumerate(movie.credits):
            self._db.execute('INSERT INTO people (tmdb_id, name) VALUES (%s, %s) '
                             'ON DUPLICATE KEY UPDATE name = VALUES(name)', (credit.person_id, credit.name))
            self._db.execute('INSERT INTO movie_credits '
                             '(movie_id, position, person_id, role_id, character_name, billing_order) '
                             'VALUES (%s, %s, %s, %s, %s, %s)',
                             (movie.tmdb_id, position, credit.person_id, roles[credit.role],
                              credit.character, credit.billing_order))
        self._db.execute('INSERT INTO movie_files (path_hash, path, movie_id) VALUES (%s, %s, %s) '
                         'ON DUPLICATE KEY UPDATE movie_id = VALUES(movie_id)',
                         (sha256(files.video.encode('utf-8')).digest(), files.video, movie.tmdb_id))
        for kind, path in (('poster', files.poster), ('backdrop', files.backdrop)):
            if path is not None:
                self._db.execute('INSERT INTO movie_artwork (path_hash, path, movie_id, kind) '
                                 'VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE movie_id = VALUES(movie_id)',
                                 (sha256(path.encode('utf-8')).digest(), path, movie.tmdb_id, kind))
