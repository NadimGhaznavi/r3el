"""Explicitly download and persist TMDB movie genres and language names."""

from r3el.activity.TMDBReferenceSchema import TMDBReferenceSchema
from r3el.interface.DbMgr import DbMgr
from r3el.interface.TMDB import TMDB
from r3el.interface.TMDBReferenceDb import TMDBReferenceDb


class TMDBReferenceRefresh:
    def __init__(self, client: TMDB, references: TMDBReferenceDb) -> None:
        self._client = client
        self._references = references

    def run(self) -> None:
        # Fetch and validate both catalogs before changing either saved catalog.
        self._references.save(self._client.reference())


if __name__ == '__main__':
    client = TMDB.from_environment()
    db = DbMgr()
    try:
        TMDBReferenceSchema(db).apply()
        TMDBReferenceRefresh(client, TMDBReferenceDb(db)).run()
    finally:
        db.close()
