"""Persist batch working data and its checkpoint events through DbMgr."""

from contextlib import contextmanager
from dataclasses import asdict, replace
import json

from r3el.entity.Identification import Identification
from r3el.entity.LogEvent import LogEvent
from r3el.entity.MediaFile import MediaFile, MediaFileIssue, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.DbMgr import DbMgr
from r3el.interface.EventLogDb import EventLogDb


class WorkspaceOccupied(RuntimeError):
    """A new batch requires an empty workspace."""


class WorkspaceActionConflict(ValueError):
    """The requested file is unavailable for a preparation decision."""


class WorkspaceBusy(RuntimeError):
    """Another operation owns the workspace."""


class WorkspaceDb:
    def __init__(self, db: DbMgr) -> None:
        self._db = db
        self._events = EventLogDb(db)

    def snapshot(self) -> MediaFileBatch | None:
        """Read the current workspace without taking the processor's exclusive lock."""
        with self._db.transaction():
            return self.load()

    def processing(self):
        """One processor per database; connection loss releases the lock."""
        return self._exclusive('workspace')

    def matching(self):
        """Freeze preparation decisions while matching, but not during identification."""
        return self._exclusive('tmdb')

    @contextmanager
    def _exclusive(self, name: str):
        acquired = self._db.query(
            "SELECT GET_LOCK(CONCAT(DATABASE(), ':', %s), 0) AS acquired", (name,),
        )[0]['acquired']
        if acquired != 1:
            raise WorkspaceBusy('The workspace is already being processed or its lock is unavailable.')
        try:
            yield
        finally:
            self._db.query("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':', %s))", (name,))

    def load(self) -> MediaFileBatch | None:
        """Load the retained batch in order, within a snapshot or processing lock."""
        rows = self._db.query('SELECT * FROM media_file_batches')
        if not rows:
            return None
        row = rows[0]
        files = self._db.query(
            'SELECT * FROM media_files WHERE batch_id = %s ORDER BY position', (row['batch_id'],),
        )
        return MediaFileBatch(
            id=row['batch_id'], requested_size=row['requested_size'],
            source_directory=row['source_directory'], state=MediaFileBatchState(row['state']),
            destination_directory=row['destination_directory'],
            started_event_id=row['started_event_id'], files=[self._file(item) for item in files],
        )

    @staticmethod
    def _file(row: dict) -> MediaFile:
        identification = json.loads(row['identification']) if row['identification'] is not None else None
        return MediaFile(
            id=row['file_id'], path=row['path'], state=MediaFileState(row['state']),
            identification=Identification(**identification) if identification is not None else None,
            issues=[MediaFileIssue(**issue) for issue in json.loads(row['issues'])],
            attempts=row['attempts'], action=MediaFileAction(row['action']),
            tmdb_match=TMDBMatch(**json.loads(row['tmdb_match'])) if row['tmdb_match'] is not None else None,
        )

    def create(self, batch: MediaFileBatch, started: LogEvent, discovered: LogEvent) -> int:
        """Commit the entire selection before any identification begins."""
        with self._db.transaction():
            event_id = self._events.record_in_transaction(started)
            self._db.execute(
                'INSERT INTO media_file_batches '
                '(batch_id, requested_size, source_directory, destination_directory, state, started_event_id) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (batch.id, batch.requested_size, batch.source_directory, batch.destination_directory,
                 batch.state, event_id),
            )
            for position, item in enumerate(batch.files):
                self._db.execute(
                    'INSERT INTO media_files '
                    '(file_id, batch_id, position, path, state, identification, issues, attempts, action) '
                    'VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, %s)',
                    (item.id, batch.id, position, item.path, item.state, '[]', item.attempts, item.action),
                )
            self._events.record_in_transaction(replace(discovered, parent_event_id=event_id))
        return event_id

    def save_file(self, batch_id: str, item: MediaFile, event: LogEvent) -> None:
        with self._db.transaction():
            self._db.execute(
                'UPDATE media_files SET state = %s, identification = %s, issues = %s, attempts = %s, action = %s '
                'WHERE batch_id = %s AND file_id = %s',
                (item.state,
                 json.dumps(asdict(item.identification), allow_nan=False) if item.identification else None,
                 json.dumps([asdict(issue) for issue in item.issues], allow_nan=False),
                 item.attempts, item.action, batch_id, item.id),
            )
            self._events.record_in_transaction(event)

    def save_action(self, batch_id: str, file_id: str, action: MediaFileAction) -> MediaFileBatch:
        """Save a user choice after the file's identification checkpoint is committed."""
        with self.matching(), self._db.transaction():
            batches = self._db.query(
                'SELECT batch_id FROM media_file_batches WHERE batch_id = %s FOR UPDATE', (batch_id,),
            )
            if not batches:
                raise WorkspaceActionConflict('The batch is no longer in the workspace.')
            files = self._db.query(
                'SELECT state FROM media_files WHERE batch_id = %s AND file_id = %s FOR UPDATE',
                (batch_id, file_id),
            )
            if not files or files[0]['state'] == MediaFileState.PENDING:
                raise WorkspaceActionConflict('The file is missing or identification has not finished.')
            self._db.execute(
                'UPDATE media_files SET tmdb_match = IF(action = %s, tmdb_match, NULL), action = %s '
                'WHERE batch_id = %s AND file_id = %s', (action, action, batch_id, file_id))
            return self.load()

    def save_match(self, batch_id: str, file_id: str, result: TMDBMatch) -> None:
        """Checkpoint one result while the caller owns the processing lock."""
        with self._db.transaction():
            self._db.execute(
                'UPDATE media_files SET tmdb_match = %s WHERE batch_id = %s AND file_id = %s',
                (json.dumps(asdict(result), allow_nan=False), batch_id, file_id),
            )

    def save_batch_state(self, batch_id: str, state: MediaFileBatchState, event: LogEvent) -> None:
        with self._db.transaction():
            self._db.execute('UPDATE media_file_batches SET state = %s WHERE batch_id = %s',
                             (state, batch_id))
            self._events.record_in_transaction(event)
