"""Prepare local media without overwriting files; remove sources only after commit."""

import filecmp
import shutil
import os
from pathlib import Path
import re
import tempfile

import httpx

from r3el.activity.MovieNaming import MovieNaming
from r3el.activity.EventWriter import EventWriter
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.entity.MovieFiles import MovieFiles


class CatalogueFiles:
    @staticmethod
    def discard_snapshot(paths: list[str]) -> list[dict]:
        files = []
        for path in paths:
            target = Path(path)
            if target.is_symlink() or not target.is_file():
                raise ValueError(f'The duplicate must be a regular file: {path}')
            stat = target.stat()
            files.append({'path': path, 'device': stat.st_dev, 'inode': stat.st_ino})
        return files

    def discard(self, files: list[dict], preferred: str) -> None:
        winner = Path(preferred)
        if winner.is_symlink() or not winner.is_file() or winner.stat().st_size == 0:
            raise ValueError('The preferred catalogue video is missing or empty; duplicates were preserved.')
        for item in files:
            target = Path(item['path'])
            if target == winner or target.is_symlink():
                raise ValueError('The duplicate path is unsafe; it has not been removed.')
            if not target.exists():
                continue  # Resume after unlink succeeded but the checkpoint failed.
            stat = target.stat()
            if (stat.st_dev, stat.st_ino) != (item['device'], item['inode']):
                raise ValueError('The duplicate file changed; it has not been removed.')
            target.unlink()
            self._sync_directory(target.parent)

    def prepare(self, movie: CatalogueMovie, source: str, destination: str | None,
                file_id: str, log: EventWriter, *, part: int | None = None, copy: bool = False, replace_existing: bool = False) -> MovieFiles:
        if not destination:
            raise ValueError('The batch needs an output directory before files can be catalogued.')
        if movie.release_date is None:
            raise ValueError('A TMDB release date is required to name the movie directory.')
        origin = Path(source)
        stem = MovieNaming.stem(movie.title, movie.release_date.year)
        folder = Path(destination).resolve() / stem
        if folder.is_symlink():
            raise ValueError('The movie directory must not be a symbolic link.')
        folder.mkdir(parents=True, exist_ok=True)
        marker = folder / '.tmdb-id'
        if marker.is_symlink():
            raise ValueError('The movie directory identity must not be a symbolic link.')
        try:
            with marker.open('x') as stream:
                stream.write(str(movie.tmdb_id))
        except FileExistsError:
            if marker.read_text() != str(movie.tmdb_id):
                raise ValueError('The title directory already belongs to a different TMDB movie.')
        target = folder / (stem + (f' Part {part}' if part is not None else '') + origin.suffix)
        if origin.is_symlink() or not origin.is_file():
            raise ValueError('The source video must be a regular file.')
        stage = self._stage(target, file_id)
        if target.is_symlink() or stage.is_symlink():
            raise ValueError('The video destination must not be a symbolic link.')
        if target.exists() and not target.is_file():
            raise ValueError('The destination media must be a regular file.')
        if target.exists() and origin != target and not replace_existing:
            if not stage.exists() or not target.samefile(stage):
                raise FileExistsError(f'The destination video already exists: {target}')
        poster = self._image(movie.poster_path, folder, 'poster', log)
        backdrop = self._image(movie.backdrop_path, folder, 'backdrop', log)
        if origin != target:
            if stage.exists():
                if not (filecmp.cmp(origin, stage, shallow=False) if copy else origin.samefile(stage)):
                    raise ValueError('The source video changed after its move was prepared.')
            else:
                # Publish a complete staged file without overwriting the destination.
                # Ordinary moves use a hard link; directory items copy their bytes.
                if copy:
                    descriptor, temporary = tempfile.mkstemp(prefix='.r3el-copy-', dir=folder)
                    try:
                        with os.fdopen(descriptor, 'wb') as output, origin.open('rb') as source_stream:
                            shutil.copyfileobj(source_stream, output)
                            output.flush()
                            os.fsync(output.fileno())
                        os.chmod(temporary, 0o644)
                        os.link(temporary, stage)
                    finally:
                        Path(temporary).unlink(missing_ok=True)
                else:
                    os.link(origin, stage)
            try:
                os.link(stage, target)
            except FileExistsError:
                if not target.samefile(stage):
                    if not replace_existing or target.is_symlink() or not target.is_file():
                        raise
                    # Keep the durable stage for retries and atomically publish its bytes.
                    replacement = stage.with_suffix('.replacement')
                    if not replacement.exists():
                        os.link(stage, replacement)
                    if replacement.is_symlink() or not replacement.samefile(stage):
                        raise ValueError('The replacement stage no longer matches the prepared media.')
                    os.replace(replacement, target)
                    log.write(Categories.File.MOVE, Names.FILE_MOVE,
                              {'outcome': 'replaced', 'source_path': str(origin),
                               'destination_path': str(target), 'error': None}, source='CatalogueFiles')
        self._sync_directory(folder)
        return MovieFiles(str(target), poster, backdrop)

    def finish(self, source: str, destination: str, file_id: str, *, preserve_source: bool = False) -> None:
        """Complete a committed move; safe to retry after source removal."""
        origin, target = Path(source), Path(destination)
        if target.is_symlink() or not target.is_file():
            raise ValueError('The catalogued destination video is missing or is a symbolic link.')
        if not preserve_source and origin != target and (origin.exists() or origin.is_symlink()):
            if origin.is_symlink() or not origin.samefile(target):
                raise ValueError('The source video changed; it has not been removed.')
            origin.unlink()
            self._sync_directory(origin.parent)
        stage = self._stage(target, file_id)
        if stage.exists():
            if stage.is_symlink() or not stage.samefile(target):
                raise ValueError('The staged video no longer matches the destination.')
            stage.unlink()
            self._sync_directory(target.parent)

    @staticmethod
    def _stage(target: Path, file_id: str) -> Path:
        return target.parent / f'.r3el-{file_id}.video'

    @staticmethod
    def _sync_directory(directory: Path) -> None:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _image(self, remote: str | None, folder: Path, kind: str, log: EventWriter) -> str | None:
        if remote is None:
            return None
        url = 'https://image.tmdb.org/t/p/original' + remote
        try:
            path, outcome = self._download_image(remote, folder, kind)
        except (OSError, ValueError, httpx.HTTPError) as error:
            log.write(Categories.Artifact.DOWNLOAD, Names.ARTIFACT_DOWNLOAD,
                      {'kind': kind, 'url': url, 'path': None, 'outcome': 'failed', 'error': str(error)},
                      source='CatalogueFiles', level='ERROR')
            raise
        log.write(Categories.Artifact.DOWNLOAD, Names.ARTIFACT_DOWNLOAD,
                  {'kind': kind, 'url': url, 'path': path, 'outcome': outcome, 'error': None},
                  source='CatalogueFiles')
        return path

    @staticmethod
    def _download_image(remote: str, folder: Path, kind: str) -> tuple[str, str]:
        if not re.fullmatch(r'/[A-Za-z0-9_-]+\.(jpg|png|webp)', remote):
            raise ValueError(f'TMDB returned an invalid {kind} path.')
        target = folder / f'{kind}-{remote[1:]}'
        if target.is_symlink():
            raise ValueError('Local artwork must not be a symbolic link.')
        if target.is_file():
            return str(target), 'reused'
        descriptor, temporary = tempfile.mkstemp(prefix='.r3el-image-', dir=folder)
        try:
            with os.fdopen(descriptor, 'wb') as output:
                with httpx.stream('GET', 'https://image.tmdb.org/t/p/original' + remote, timeout=30) as response:
                    response.raise_for_status()
                    if not response.headers.get('content-type', '').startswith('image/'):
                        raise ValueError('TMDB did not return an image.')
                    for chunk in response.iter_bytes():
                        output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if Path(temporary).stat().st_size == 0:
                raise ValueError('TMDB returned an empty image.')
            os.chmod(temporary, 0o644)
            os.link(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return str(target), 'downloaded'
