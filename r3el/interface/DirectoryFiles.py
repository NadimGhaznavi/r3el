"""Capture GNU find listings and unambiguous filesystem metadata on the server."""

import os
from pathlib import Path
import subprocess
import tempfile


class DirectoryFiles:
    def directories(self, root: str, destination: str | None) -> list[Path]:
        excluded = Path(destination).resolve() if destination else None
        with os.scandir(root) as entries:
            return sorted((Path(entry.path) for entry in entries
                           if entry.is_dir(follow_symlinks=False) and Path(entry.path).resolve() != excluded),
                          key=lambda path: path.name)

    def scan(self, directory: Path, destination: str | None = None) -> tuple[str, list[tuple[str, int]]]:
        prune = ['-path', str(Path(destination).resolve()), '-prune', '-o'] if destination else []
        with tempfile.NamedTemporaryFile() as metadata:
            result = subprocess.run(
                ['find', str(directory), *prune, '-ls', '-fprintf', metadata.name, r'%y\0%s\0%p\0'],
                capture_output=True, check=True, env={**os.environ, 'LC_ALL': 'C'},
            )
            fields = Path(metadata.name).read_bytes().split(b'\0')[:-1]
        files = [(os.fsdecode(fields[index + 2]), int(fields[index + 1]))
                 for index in range(0, len(fields), 3) if fields[index] == b'f']
        return result.stdout.decode('utf-8', errors='replace'), files
