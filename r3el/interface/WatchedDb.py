"""Record movie and episode viewings through the shared database interface."""

from r3el.interface.DbMgr import DbMgr


class WatchedDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db

    def record(self, media_type: str, media_id: int) -> bool:
        """Append a viewing, returning False when the catalogue entry is absent."""
        table, column = {'movie': ('movies', 'movie_id'),
                         'episode': ('tv_episodes', 'episode_id')}[media_type]
        return self._db.execute(
            f'INSERT INTO watched ({column}, watched_at) '
            f'SELECT tmdb_id, UTC_TIMESTAMP(6) FROM {table} WHERE tmdb_id = %s',
            (media_id,)) == 1
