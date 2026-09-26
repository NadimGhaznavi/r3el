"""Remove a catalogued source directory after verifying its copied media."""

import os
from pathlib import Path
import shutil
import time

from r3el.activity.EventWriter import EventWriter
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names


class SourceDirectoryCleanup:
    def finish(self, source: str, copies: list[dict], *, preserve_directory: bool, log: EventWriter) -> None:
        directory = Path(source)
        if directory.is_symlink():
            raise ValueError('The source directory must not be a symbolic link.')
        root = directory.resolve()
        # Verify every copied file before removing any source file.
        for copy in copies:
            origin, target = Path(copy['source']), Path(copy['destination'])
            if not origin.resolve().is_relative_to(root) or target.resolve().is_relative_to(root):
                raise ValueError('Source cleanup requires separate source and destination directories.')
            if target.is_symlink() or not target.is_file():
                raise ValueError(f'The copied destination is missing or unsafe: {target}')
            if origin.exists() or origin.is_symlink():
                if origin.is_symlink() or not origin.is_file() or not self._verify(origin, target, log):
                    raise ValueError(f'The source and copied destination do not match: {origin}')
        for copy in copies:
            Path(copy['source']).unlink(missing_ok=True)
        if not directory.exists():
            return
        if not preserve_directory:
            shutil.rmtree(directory)
        else:
            # Keep unresolved subtitles and other remaining files; prune only empty children.
            for current, _, _ in os.walk(directory, topdown=False, followlinks=False):
                child = Path(current)
                if child != directory and not any(child.iterdir()):
                    child.rmdir()

    @staticmethod
    def _verify(origin: Path, target: Path, log: EventWriter) -> bool:
        size = origin.stat().st_size
        data = {'source_path': str(origin), 'destination_path': str(target), 'total_bytes': size}
        log.write(Categories.File.MOVE, Names.FILE_COPY,
                  {**data, 'outcome': 'verifying', 'verified_bytes': 0}, source='SourceDirectoryCleanup')
        if target.stat().st_size != size:
            return False
        verified = 0
        last_report = time.monotonic()
        with origin.open('rb') as source_stream, target.open('rb') as target_stream:
            while True:
                source_chunk = source_stream.read(1024 * 1024)
                target_chunk = target_stream.read(1024 * 1024)
                if source_chunk != target_chunk:
                    return False
                if not source_chunk:
                    break
                verified += len(source_chunk)
                now = time.monotonic()
                if now - last_report >= 5:
                    log.write(Categories.File.MOVE, Names.FILE_COPY,
                              {**data, 'outcome': 'verifying', 'verified_bytes': verified},
                              source='SourceDirectoryCleanup')
                    last_report = now
        log.write(Categories.File.MOVE, Names.FILE_COPY,
                  {**data, 'outcome': 'verified', 'verified_bytes': verified}, source='SourceDirectoryCleanup')
        return True
