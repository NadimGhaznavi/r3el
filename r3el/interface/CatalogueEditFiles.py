"""Stage replacement movie files and restore originals on transaction failure."""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4

from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.CatalogueFileDeletion import CatalogueFileDeletion


class CatalogueEditFiles:
    def __init__(self) -> None:
        self._published = None
        self._backups = []

    @contextmanager
    def replacing(self):
        try:
            yield self
        except BaseException:
            for original, backup in self._backups:
                if not original.exists():
                    os.link(backup, original)
            if self._published is not None:
                shutil.rmtree(self._published)
            raise
        finally:
            for _, backup in self._backups:
                backup.unlink(missing_ok=True)

    def prepare(self, movie, entries: list[dict], log) -> MovieFiles:
        videos = [entry for entry in entries if entry['kind'] == 'video']
        if not videos:
            raise ValueError('The movie has no video files to relabel.')
        old_folder = Path(videos[0]['path']).parent
        if any(parent.is_symlink() for parent in (old_folder, *old_folder.parents)):
            raise ValueError('The movie directory must not contain symbolic links.')
        files = CatalogueFiles()
        with TemporaryDirectory(prefix='.r3el-edit-', dir=old_folder.parent) as temporary:
            associated = []
            for position, entry in enumerate(entries):
                stage_id = str(position)
                prepared = files.prepare(movie, entry['path'], temporary, stage_id, log, part=entry['part'])
                files.finish(entry['path'], prepared.video, stage_id, preserve_source=True)
                associated.append(dict(entry, path=prepared.video))
            staged_folder = Path(prepared.video).parent
            target = old_folder.parent / staged_folder.name
            # Two TMDB entries can have exactly the same title and release year.
            if target == old_folder:
                target = target.with_name(f'{target.name} [TMDB {movie.tmdb_id}]')
            target.mkdir()  # Claim a new directory; never overwrite existing media.
            self._published = target
            os.replace(staged_folder, target)
            def relocated(path):
                return str(target / Path(path).name) if path else None
            return MovieFiles(relocated(associated[0]['path']), relocated(prepared.poster),
                              relocated(prepared.backdrop),
                              [dict(entry, path=relocated(entry['path'])) for entry in associated])

    def remove(self, paths: list[str]) -> None:
        # Keep a second name for every inode until the database commit succeeds.
        # Backups live beside their originals so hard links stay on one filesystem.
        CatalogueFileDeletion.validate(paths)
        for path in paths:
            original = Path(path)
            if original.is_file() and not original.is_symlink():
                backup = original.with_name(f'.r3el-edit-{uuid4().hex}.backup')
                os.link(original, backup)
                self._backups.append((original, backup))
        CatalogueFileDeletion().remove(paths)
