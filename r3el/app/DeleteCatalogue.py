"""Remove a movie, TV show, or season and its catalogued files."""

from r3el.interface.CatalogueDeletionDb import CatalogueDeletionDb
from r3el.interface.CatalogueFileDeletion import CatalogueFileDeletion


class DeleteCatalogue:
    def __init__(self, catalogue: CatalogueDeletionDb, files: CatalogueFileDeletion) -> None:
        self._catalogue = catalogue
        self._files = files

    def run(self, media_type: str, media_id: int, season: int | None = None) -> bool:
        with self._catalogue.deleting(media_type, media_id, season) as paths:
            if paths is None:
                return False
            self._files.remove(paths)
        return True
