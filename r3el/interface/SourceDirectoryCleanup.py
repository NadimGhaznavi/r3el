"""Remove a catalogued source directory after committing its filesystem moves."""

import os
from pathlib import Path

from r3el.interface.DirectoryFiles import DirectoryFiles


class SourceDirectoryCleanup:
    def finish(self, source: str, moves: list[dict], *, preserve_directory: bool) -> None:
        directory = Path(source)
        if directory.is_symlink():
            raise ValueError('The source directory must not be a symbolic link.')
        root = directory.resolve()
        # Check every destination inode before removing any source file.
        for move in moves:
            origin, target = Path(move['source']), Path(move['destination'])
            if not origin.resolve().is_relative_to(root) or target.resolve().is_relative_to(root):
                raise ValueError('Source cleanup requires separate source and destination directories.')
            if target.is_symlink() or not target.is_file():
                raise ValueError(f'The move destination is missing or unsafe: {target}')
            if origin.exists() or origin.is_symlink():
                if origin.is_symlink() or not origin.is_file() or not origin.samefile(target):
                    raise ValueError(f'The source and move destination do not match: {origin}')
        for move in moves:
            Path(move['source']).unlink(missing_ok=True)
        if not directory.exists():
            return
        if not preserve_directory:
            DirectoryFiles().remove_without_media(str(directory))
        else:
            # Keep unresolved subtitles and other remaining files; prune only empty children.
            for current, _, _ in os.walk(directory, topdown=False, followlinks=False):
                child = Path(current)
                if child != directory and not any(child.iterdir()):
                    child.rmdir()
