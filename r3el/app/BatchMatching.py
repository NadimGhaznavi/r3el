"""Match approved identifications and checkpoint downloaded TMDB results."""

from collections.abc import Callable
from dataclasses import asdict

from r3el.activity.BatchPreparation import BatchPreparation
from r3el.activity.EventWriter import EventWriter
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.LogEvent import LogEvent
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceActionConflict


class BatchMatching:
    def __init__(self, workspace: WorkspaceDb, record: Callable[[LogEvent], int]) -> None:
        self._workspace = workspace
        self._record = record

    def run(self, batch_id: str) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            if batch is None or batch.id != batch_id or not BatchPreparation.ready(batch):
                raise WorkspaceActionConflict('Resolve every file action after identification finishes.')
            client = None
            for item in batch.files:
                log = EventWriter(self._record,
                                  {'batch_id': batch.id, 'item_id': item.id, 'filename': item.filename},
                                  batch.started_event_id)
                identification = item.identification
                title = identification.title if identification is not None else None
                year = identification.year if identification is not None else None
                if item.action in (MediaFileAction.IGNORE, MediaFileAction.DELETE):
                    result = TMDBMatch(title, year, skipped=True)
                elif (item.tmdb_match is not None and item.tmdb_match.response is not None
                      and item.tmdb_match.title == title and item.tmdb_match.year == year):
                    # Repeated submissions reuse completed queries; failed searches can be retried.
                    continue
                elif identification is None:
                    result = TMDBMatch(title, year, error='No identified title and year available.')
                else:
                    try:
                        if client is None:
                            client = TMDB.from_environment()
                        log.parent_event_id = log.write(
                            Categories.TMDB.SEARCH, Names.TMDB_SEARCH,
                            {'url': TMDB.URL, 'parameters': TMDB.search_parameters(title, year)},
                            source='TMDB')
                        result = TMDBMatch(title, year, response=client.search(title, year))
                    except TMDBError as error:
                        result = TMDBMatch(title, year, error=str(error))
                event = None if result.skipped else log.prepare(
                    Categories.TMDB.RESULT, Names.TMDB_RESULT,
                    dict(asdict(result), outcome=result.label), source='TMDB',
                    level='ERROR' if result.error is not None else 'INFO')
                self._workspace.save_match(batch.id, item.id, result, event)
