"""Filesystem bridge for retrieving filenames from a directory."""

from heapq import nsmallest
import os
from pathlib import Path


class FileMgr:
    def __init__(self, directory: str | Path) -> None:
        self._directory = directory

    def filenames(self, limit: int) -> list[str]:
        """Return up to limit regular filenames in alphabetical order.

        Scan the directory afresh on each call. Subdirectories and symbolic
        links are excluded. Filesystem errors propagate to the caller.
        """
        with os.scandir(self._directory) as entries:
            return nsmallest(
                limit,
                (entry.name for entry in entries if entry.is_file(follow_symlinks=False)),
            )
