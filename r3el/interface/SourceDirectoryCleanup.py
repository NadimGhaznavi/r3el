"""Remove a catalogued source directory after verifying its copied media."""

import filecmp
import os
from pathlib import Path
import shutil


class SourceDirectoryCleanup:
    def finish(self, source: str, copies: list[dict], *, preserve_directory: bool) -> None:
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
                if origin.is_symlink() or not origin.is_file() or not filecmp.cmp(origin, target, shallow=False):
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
