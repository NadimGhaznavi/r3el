"""Delete catalogue hierarchies within a transaction owned by this interface."""

from contextlib import contextmanager
from hashlib import sha256

from r3el.interface.DbMgr import DbMgr


class CatalogueDeletionDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    @contextmanager
    def deleting(self, media_type: str, media_id: int, season: int | None = None):
        """Yield unshared file paths; a file removal failure rolls back the records.

        None means the requested entry does not exist. Keep the parent locked
        until file removal completes, so imports cannot attach new children.
        """
        with self._db.transaction():
            table = 'movies' if media_type == 'movie' else 'tv_series'
            if not self._db.query(f'SELECT tmdb_id FROM {table} WHERE tmdb_id=%s FOR UPDATE', (media_id,)):
                yield None
                return
            if media_type == 'movie':
                paths = self._db.query('SELECT path FROM movie_files WHERE movie_id=%s UNION '
                                       'SELECT path FROM movie_artwork WHERE movie_id=%s', (media_id, media_id))
                for child in ('watched', 'movie_files', 'movie_artwork', 'movie_credits', 'movie_genres'):
                    self._db.execute(f'DELETE FROM {child} WHERE movie_id=%s', (media_id,))
                self._db.execute('DELETE FROM movies WHERE tmdb_id=%s', (media_id,))
            else:
                params = (media_id,) if season is None else (media_id, season)
                scope = 'series_id=%s' + ('' if season is None else ' AND season_number=%s')
                if season is not None and not self._db.query(
                        'SELECT season_number FROM tv_seasons WHERE ' + scope + ' FOR UPDATE', params):
                    yield None
                    return
                episodes = 'SELECT tmdb_id FROM tv_episodes WHERE ' + scope
                # Stills may carry only an episode ID, rather than a season number.
                art_scope = '(' + scope + ') OR episode_id IN (' + episodes + ')'
                paths = self._db.query('SELECT path FROM tv_episode_files WHERE episode_id IN (' + episodes
                                       + ') UNION SELECT path FROM tv_artwork WHERE ' + art_scope, params * 3)
                for child in ('watched', 'tv_episode_files', 'tv_episode_credits'):
                    self._db.execute(f'DELETE FROM {child} WHERE episode_id IN (' + episodes + ')', params)
                self._db.execute('DELETE FROM tv_artwork WHERE ' + art_scope, params * 2)
                self._db.execute('DELETE FROM tv_episodes WHERE ' + scope, params)
                self._db.execute('DELETE FROM tv_seasons WHERE ' + scope, params)
                if season is None:
                    for child in ('tv_series_credits', 'tv_series_genres'):
                        self._db.execute(f'DELETE FROM {child} WHERE series_id=%s', (media_id,))
                    self._db.execute('DELETE FROM tv_series WHERE tmdb_id=%s', (media_id,))
            unshared = []
            for row in paths:
                path = row['path']
                fingerprint = sha256(path.encode()).digest()
                remaining = self._db.query(' UNION ALL '.join(
                    f'SELECT path FROM {child} WHERE path_hash=%s'
                    for child in ('movie_files', 'movie_artwork', 'tv_episode_files', 'tv_artwork')),
                    (fingerprint,) * 4)
                if not remaining:
                    unshared.append(path)
            yield unshared
