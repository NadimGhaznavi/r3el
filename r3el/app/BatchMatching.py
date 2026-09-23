"""Match available identifications and checkpoint downloaded TMDB results."""

from collections.abc import Callable
from dataclasses import asdict, replace

from r3el.activity.BatchPreparation import BatchPreparation
from r3el.activity.EventWriter import EventWriter
from r3el.app.MovieSelection import MovieSelection
from r3el.app.RetryIdentification import RetryIdentification
from r3el.constants.DR3el import DR3el
from r3el.entity.MediaFile import MediaFileState
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.LogEvent import LogEvent
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceActionConflict


class BatchMatching:
    def __init__(self, workspace: WorkspaceDb, record: Callable[[LogEvent], int]) -> None:
        self._workspace = workspace
        self._record = record

    def run(self, batch_id: str) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            if batch is None or batch.id != batch_id or not BatchPreparation.ready(batch):
                raise WorkspaceActionConflict('Processing requires a nonempty batch with identification finished.')
            for item in batch.files:
                log = EventWriter(self._record,
                                  {'batch_id': batch.id, 'item_id': item.id, 'filename': item.filename},
                                  batch.started_event_id)
                if (item.retries > 0 and item.state == MediaFileState.UNRESOLVED_LLM
                        and item.action not in (MediaFileAction.IGNORE, MediaFileAction.DELETE)):
                    continue
                identification = item.identification
                title = identification.title if identification is not None else None
                year = identification.year if identification is not None else None
                if item.action in (MediaFileAction.IGNORE, MediaFileAction.DELETE):
                    result = TMDBMatch(title, year, skipped=True)
                elif (item.tmdb_match is not None and item.tmdb_match.response is not None
                      and item.tmdb_match.title == title and item.tmdb_match.year == year):
                    # Repeated submissions reuse completed queries; failed searches can be retried.
                    result = item.tmdb_match
                    if result.response['total_results'] == 1 or result.selected_number is not None:
                        continue
                elif identification is None:
                    result = TMDBMatch(title, year, error='No identified title and year available.')
                else:
                    result = self._search(title, year, log)
                while (result.response is not None and not result.skipped and result.error is None
                       and result.response['total_results'] == 0):
                    item.tmdb_match = result
                    self._workspace.save_match(batch.id, item.id, result, log.prepare(
                        Categories.TMDB.RESULT, Names.TMDB_RESULT,
                        dict(asdict(result), outcome=result.label), source='TMDB'))
                    retry = RetryIdentification(self._workspace)
                    if item.retries >= DR3el.MAX_IDENTIFICATION_RETRIES:
                        retry.exhausted(item, log)
                        break
                    retry.run(item, log)
                    if item.state != MediaFileState.IDENTIFIED:
                        break
                    result = self._search(item.identification.title, item.identification.year, log)
                if not result.skipped and item.retries > 0 and item.state == MediaFileState.UNRESOLVED_LLM:
                    continue
                needs_selection = (result.response is not None and not result.skipped and result.error is None
                                   and result.response['total_results'] > 1 and result.selected_number is None)
                if needs_selection:
                    result = replace(result, selection_pending=True, selection_error=None)
                event = None if result.skipped else log.prepare(
                    Categories.TMDB.RESULT, Names.TMDB_RESULT,
                    dict(asdict(result), outcome=result.label), source='TMDB',
                    level='ERROR' if result.error is not None else 'INFO')
                self._workspace.save_match(batch.id, item.id, result, event)
                if needs_selection:
                    try:
                        result = MovieSelection(LLM.from_environment()).run(result, log)
                    except BaseException:
                        self._workspace.save_match(batch.id, item.id,
                                                   replace(result, selection_pending=False), None)
                        raise
                    result = replace(result, selection_pending=False)
                    event = log.prepare(Categories.TMDB.RESULT, Names.TMDB_RESULT,
                                        dict(asdict(result), outcome=result.label), source='MovieSelection',
                                        level='ERROR' if result.selection_error else 'INFO')
                    self._workspace.save_match(batch.id, item.id, result, event)

    @staticmethod
    def _search(title: str, year: int, log: EventWriter) -> TMDBMatch:
        try:
            client = TMDB.from_environment()
            log.parent_event_id = log.write(
                Categories.TMDB.SEARCH, Names.TMDB_SEARCH,
                {'url': TMDB.URL, 'parameters': TMDB.search_parameters(title, year)}, source='TMDB')
            return TMDBMatch(title, year, response=client.search(title, year))
        except TMDBError as error:
            return TMDBMatch(title, year, error=str(error))
