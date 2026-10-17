"""Remove explicitly catalogued files without traversing linked directories."""

from pathlib import Path


class CatalogueFileDeletion:
    @staticmethod
    def validate(paths: list[str]) -> None:
        targets = [Path(path) for path in paths]
        for target in targets:
            if (not target.is_absolute() or '..' in target.parts
                    or any(parent.is_symlink() for parent in (target, *target.parents))):
                raise ValueError('A catalogued file has an unsafe path.')
            if target.exists() and not target.is_file():
                raise ValueError('A catalogued path is not a regular file.')

    def remove(self, paths: list[str]) -> None:
        self.validate(paths)
        for target in map(Path, paths):
            # A retry can follow partial file removal or a failed database commit.
            target.unlink(missing_ok=True)
