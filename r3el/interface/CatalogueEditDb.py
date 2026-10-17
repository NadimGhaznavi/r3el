"""Replace a movie identity and its related records in one transaction."""

from contextlib import contextmanager
from hashlib import sha256

from r3el.interface.CatalogueDb import CatalogueDb
from r3el.interface.DbMgr import DbMgr


class CatalogueEditDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    @contextmanager
    def editing(self, old_id: int, new_id: int):
        with self._db.transaction():
            rows = self._db.query('SELECT * FROM movies WHERE tmdb_id=%s FOR UPDATE', (old_id,))
            if not rows:
                raise ValueError('The movie is no longer in the catalogue.')
            if self._db.query('SELECT tmdb_id FROM movies WHERE tmdb_id=%s FOR UPDATE', (new_id,)):
                raise ValueError('The new TMDB ID is already in the catalogue.')
            movie = rows[0]
            movie['files'] = self._db.query(
                'SELECT path,kind,part FROM movie_files WHERE movie_id=%s ORDER BY part,path', (old_id,))
            yield movie

    def replace_in_transaction(self, old: dict, movie, files) -> list[str]:
        old_id = old['tmdb_id']
        paths = self._db.query('SELECT path FROM movie_files WHERE movie_id=%s UNION '
                               'SELECT path FROM movie_artwork WHERE movie_id=%s', (old_id, old_id))
        CatalogueDb(self._db).save_in_transaction(movie, files)
        self._db.execute('UPDATE movies SET added_at=%s WHERE tmdb_id=%s', (old['added_at'], movie.tmdb_id))
        self._db.execute('UPDATE watched SET movie_id=%s WHERE movie_id=%s', (movie.tmdb_id, old_id))
        for table in ('movie_files', 'movie_artwork', 'movie_credits', 'movie_genres'):
            self._db.execute(f'DELETE FROM {table} WHERE movie_id=%s', (old_id,))
        self._db.execute('DELETE FROM movies WHERE tmdb_id=%s', (old_id,))
        unshared = []
        for row in paths:
            path = row['path']
            remaining = self._db.query(' UNION ALL '.join(
                f'SELECT path FROM {table} WHERE path_hash=%s'
                for table in ('movie_files', 'movie_artwork', 'tv_episode_files', 'tv_artwork')),
                (sha256(path.encode()).digest(),) * 4)
            if not remaining:
                unshared.append(path)
        return unshared
