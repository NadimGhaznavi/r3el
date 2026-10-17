"""Correct an imported movie's TMDB match while preserving its media and history."""

from r3el.interface.CatalogueEditDb import CatalogueEditDb
from r3el.interface.CatalogueEditFiles import CatalogueEditFiles
from r3el.interface.TMDBCatalogue import TMDBCatalogue


class EditCatalogueMovie:
    def __init__(self, catalogue: CatalogueEditDb, files: CatalogueEditFiles, tmdb: TMDBCatalogue, log) -> None:
        self._catalogue = catalogue
        self._files = files
        self._tmdb = tmdb
        self._log = log

    def run(self, old_id: int, new_id: int) -> None:
        if old_id == new_id:
            raise ValueError('Enter a different TMDB movie ID.')
        movie = self._tmdb.movie(new_id)
        with self._files.replacing():
            with self._catalogue.editing(old_id, new_id) as old:
                files = self._files.prepare(movie, old['files'], self._log)
                obsolete = self._catalogue.replace_in_transaction(old, movie, files)
                self._files.remove(obsolete)
