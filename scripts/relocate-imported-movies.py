#!/usr/bin/env python3
"""One-time repair for movies imported directly into the media directory.

Run from the checkout with R3el's Python environment. Preview by default;
--apply moves whole movie directories and updates local catalogue paths.
Stop processing and clear the workspace first.
"""
import argparse
from hashlib import sha256
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3el.interface.DbMgr import DbMgr
from r3el.interface.WorkspaceDb import WorkspaceDb


class ImportedMovieRepair:
    def __init__(self, db):
        self.db = db

    def run(self, root: Path, apply: bool = False):
        root = root.resolve(strict=True)
        destination = root / 'movies'
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError(f'Expected a real movies directory: {destination}')
        moves = []
        for source in sorted(root.iterdir()):
            if source.name in ('movies', 'music', 'tv', 'tv-shows'):
                continue
            if source.is_symlink() or not source.is_dir():
                continue
            marker = source / '.tmdb-id'
            if marker.is_symlink() or not marker.is_file():
                continue
            movie_id = int(marker.read_text().strip())
            target = destination / source.name
            if target.exists() or target.is_symlink():
                raise ValueError(f'Destination already exists; nothing moved: {target}')
            if source.stat().st_dev != destination.stat().st_dev:
                raise ValueError('Repair requires source and destination on the same filesystem.')
            moves.append((source, target, movie_id))

        updates = []
        for table in ('movie_files', 'movie_artwork'):
            rows = self.db.query(f'SELECT * FROM {table}')
            by_path = {row['path']: row for row in rows}
            for row in rows:
                old = Path(row['path'])
                for source, target, movie_id in moves:
                    if old.is_relative_to(source):
                        if row['movie_id'] != movie_id or not old.is_file():
                            raise ValueError(f'Catalogue identity or file mismatch: {old}')
                        new = str(target / old.relative_to(source))
                        existing = by_path.get(new)
                        if existing is not None:
                            metadata = lambda record: {key: value for key, value in record.items()
                                                       if key not in ('path', 'path_hash')}
                            if metadata(existing) != metadata(row):
                                raise ValueError(f'Conflicting destination catalogue record: {new}')
                        updates.append((table, row['path_hash'], new, existing is not None))
                        break
        for source, target, movie_id in moves:
            print(f'{source} -> {target} (TMDB {movie_id})')
        print(f'{len(moves)} directories; {len(updates)} catalogue paths. '
              + ('Applying.' if apply else 'Preview only; use --apply to move.'))
        if not apply:
            return
        moved = []
        try:
            with self.db.transaction():
                for source, target, _ in moves:
                    if target.exists() or target.is_symlink():
                        raise ValueError(f'Destination appeared during repair: {target}')
                    source.rename(target)
                    moved.append((source, target))
                for table, old_hash, new, already_catalogued in updates:
                    if already_catalogued:
                        self.db.execute(f'DELETE FROM {table} WHERE path_hash = %s', (old_hash,))
                        continue
                    self.db.execute(
                        f'UPDATE {table} SET path = %s, path_hash = %s WHERE path_hash = %s',
                        (new, sha256(new.encode('utf-8')).digest(), old_hash))
        except BaseException:
            for source, target in reversed(moved):
                target.rename(source)
            raise
        print('Repair completed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--media-root', type=Path, default=Path('/exports/disk1/archive/media'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    for line in Path('/etc/r3el/database.env').read_text().splitlines():
        key, value = line.split('=', 1)
        os.environ[key] = value
    db = DbMgr()
    try:
        if WorkspaceDb(db).snapshot() is not None:
            raise ValueError('Stop processing and Clear Current Batch before running the repair.')
        ImportedMovieRepair(db).run(args.media_root, args.apply)
    finally:
        db.close()


if __name__ == '__main__':
    main()
