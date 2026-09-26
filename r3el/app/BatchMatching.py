"""Match available identifications and checkpoint downloaded TMDB results."""

from collections.abc import Callable
from dataclasses import asdict, replace

import httpx

from r3el.activity.BatchPreparation import BatchPreparation
from r3el.activity.MovieFormats import MovieFormats
from r3el.activity.DirectoryMediaMove import DirectoryMediaMove
from r3el.activity.EventWriter import EventWriter
from r3el.app.MovieSelection import MovieSelection
from r3el.app.RetryIdentification import RetryIdentification
from r3el.constants.DR3el import DR3el
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.entity.MediaFileBatch import MediaFileBatch
from r3el.entity.MediaFileBatch import MediaFileBatchState
from r3el.entity.BatchStopped import BatchStopped
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.LogEvent import LogEvent
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.DirectoryFiles import DirectoryFiles
from r3el.interface.SourceDirectoryCleanup import SourceDirectoryCleanup
from r3el.interface.LLM import LLM
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceActionConflict


class BatchMatching:
    def __init__(self, workspace: WorkspaceDb, record: Callable[[LogEvent], int], llm: LLM | None = None) -> None:
        self._workspace = workspace
        self._record = record
        self._llm = llm

    def replace_media(self, batch_id: str, file_id: str) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            if batch is None or batch.id != batch_id or batch.in_progress:
                raise WorkspaceActionConflict('Replacing media requires a finished batch.')
            item = next((item for item in batch.files if item.id == file_id), None)
            if (item is None or item.tmdb_match is None or not item.tmdb_match.entry_exists
                    or item.action in (MediaFileAction.IGNORE, MediaFileAction.DELETE)):
                raise WorkspaceActionConflict('The item no longer has a destination conflict.')
            log = EventWriter(self._record, {'batch_id': batch_id, 'item_id': file_id,
                                            'filename': item.filename}, batch.started_event_id)
            result = replace(item.tmdb_match, replace_local_media=True)
            self._workspace.save_match(batch_id, file_id, result, log.prepare(
                Categories.File.MOVE, Names.FILE_MOVE, {'outcome': 'replacement_requested',
                    'source_path': item.path, 'destination_path': None, 'error': None}, source='BatchMatching'))
            self._catalogue(batch, item, result, log)

    def match_id(self, batch_id: str, file_id: str, movie_id: int) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            if batch is None or batch.id != batch_id or batch.in_progress:
                raise WorkspaceActionConflict('Manual matching requires a finished batch.')
            item = next((item for item in batch.files if item.id == file_id), None)
            if (item is None or item.tmdb_match is None or not item.tmdb_match.needs_manual_match
                    or item.action in (MediaFileAction.IGNORE, MediaFileAction.DELETE)):
                raise WorkspaceActionConflict('The file no longer needs a manual match.')
            log = EventWriter(self._record, {'batch_id': batch_id, 'item_id': file_id,
                                            'filename': item.filename}, batch.started_event_id)
            try:
                data = TMDB.from_environment().details(movie_id)
                movie = TMDBCatalogue.from_details(data, movie_id)
            except TMDBError as error:
                result = replace(item.tmdb_match, selection_error=str(error))
                self._workspace.save_match(batch_id, file_id, result, log.prepare(
                    Categories.TMDB.RESULT, Names.TMDB_RESULT,
                    {'outcome': 'Manual match failed', 'movie_id': movie_id, 'error': str(error)},
                    source='ManualMatch', level='ERROR'))
                return
            result = TMDBMatch(item.tmdb_match.title, item.tmdb_match.year,
                               response={'results': [dict(data, genre_ids=[genre.id for genre in movie.genres])],
                                         'total_results': 1, 'total_pages': 1, 'page': 1})
            self._workspace.save_match(batch_id, file_id, result, log.prepare(
                Categories.TMDB.RESULT, Names.TMDB_RESULT,
                {'outcome': 'Manual match selected', 'movie_id': movie_id, 'error': None,
                 'response': result.response}, source='ManualMatch'))
            self._catalogue(batch, item, result, log, movie=movie)

    def run(self, batch_id: str, *, file_ids: list[str] | None = None) -> None:
        try:
            self._run(batch_id, file_ids=file_ids)
        except BatchStopped:
            batch = self._workspace.load()
            log = EventWriter(self._record, {'batch_id': batch_id}, batch.started_event_id)
            self._workspace.save_batch_state(batch_id, MediaFileBatchState.CANCELLED, log.prepare(
                Categories.Batch.LIFECYCLE, Names.BATCH_CANCELLED,
                {'stage': 'matching'}, source='BatchMatching', level='WARNING'))
            raise

    def _run(self, batch_id: str, *, file_ids: list[str] | None = None) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            self._workspace.check_stop(batch_id)
            if batch is not None and file_ids is not None:
                batch = replace(batch, files=[item for item in batch.files if item.id in file_ids])
            if batch is None or batch.id != batch_id or not BatchPreparation.ready(batch):
                raise WorkspaceActionConflict('Processing requires a nonempty batch with identification finished.')
            for item in batch.files:
                self._workspace.check_stop(batch_id)
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
                elif (item.tmdb_match is not None
                      and (item.tmdb_match.response is not None or item.tmdb_match.year_offset != 0)
                      and item.tmdb_match.title == title
                      and item.tmdb_match.year - item.tmdb_match.year_offset == year):
                    # Repeated submissions reuse completed queries; failed searches can be retried.
                    result = item.tmdb_match
                    if ((result.response is not None and result.response['total_results'] == 1)
                            or result.selected_number is not None):
                        self._catalogue(batch, item, result, log)
                        continue
                elif identification is None:
                    result = TMDBMatch(title, year, error='No identified title and year available.')
                else:
                    result = self._search(title, year, log)
                if result.year_offset != 0:
                    result = self._search_adjacent_years(batch, item, result, log)
                while (result.response is not None and not result.skipped and result.error is None
                       and result.response['total_results'] == 0 and result.year_offset == 0):
                    item.tmdb_match = result
                    self._workspace.save_match(batch.id, item.id, result, log.prepare(
                        Categories.TMDB.RESULT, Names.TMDB_RESULT,
                        dict(asdict(result), outcome=result.label), source='TMDB'))
                    self._workspace.check_stop(batch_id)
                    retry = RetryIdentification(self._workspace, self._llm)
                    if item.retries >= DR3el.MAX_IDENTIFICATION_RETRIES:
                        result = self._search_adjacent_years(batch, item, result, log)
                        break
                    retry.run(item, log)
                    self._workspace.check_stop(batch_id)
                    if item.state != MediaFileState.IDENTIFIED:
                        break
                    result = self._search(item.identification.title, item.identification.year, log)
                if not result.skipped and item.retries > 0 and item.state == MediaFileState.UNRESOLVED_LLM:
                    continue
                needs_selection = (result.response is not None and not result.skipped and result.error is None
                                   and result.response['total_results'] > 1 and result.selected_number is None)
                if needs_selection:
                    result = replace(result, selection_pending=True, selection_error=None)
                event = None if result.skipped or result.year_offset != 0 else log.prepare(
                    Categories.TMDB.RESULT, Names.TMDB_RESULT,
                    dict(asdict(result), outcome=result.label), source='TMDB',
                    level='ERROR' if result.error is not None else 'INFO')
                self._workspace.save_match(batch.id, item.id, result, event)
                if needs_selection:
                    try:
                        result = MovieSelection(self._llm or LLM.from_environment()).run(result, log)
                    except BaseException:
                        self._workspace.save_match(batch.id, item.id,
                                                   replace(result, selection_pending=False), None)
                        raise
                    result = replace(result, selection_pending=False)
                    event = log.prepare(Categories.TMDB.RESULT, Names.TMDB_RESULT,
                                        dict(asdict(result), outcome=result.label), source='MovieSelection',
                                        level='ERROR' if result.selection_error else 'INFO')
                    self._workspace.save_match(batch.id, item.id, result, event)
                self._catalogue(batch, item, result, log)
            self._workspace.check_stop(batch_id)

    def _search_adjacent_years(self, batch: MediaFileBatch, item: MediaFile,
                               result: TMDBMatch, log: EventWriter) -> TMDBMatch:
        if result.error is None and result.response is not None and result.response['total_results'] > 0:
            return result
        year = result.year - result.year_offset
        offsets = (-1, 1)
        start = 0 if result.year_offset == 0 else offsets.index(result.year_offset)
        if result.year_offset != 0 and result.error is None:
            start += 1
        for offset in offsets[start:]:
            self._workspace.check_stop(batch.id)
            self._workspace.save_match(batch.id, item.id, replace(result, selection_pending=True), None)
            try:
                result = replace(self._search(result.title, year + offset, log), year_offset=offset)
            except BaseException:
                self._workspace.save_match(batch.id, item.id, replace(result, selection_pending=False), None)
                raise
            item.tmdb_match = result
            self._workspace.save_match(batch.id, item.id, result, log.prepare(
                Categories.TMDB.RESULT, Names.TMDB_RESULT,
                dict(asdict(result), outcome=result.label), source='TMDB',
                level='ERROR' if result.error else 'INFO'))
            if result.error is not None or result.response['total_results'] > 0:
                return result
        item.tmdb_match = result
        RetryIdentification(self._workspace, self._llm).exhausted(item, log)
        return result

    def _catalogue(self, batch: MediaFileBatch, item: MediaFile, result: TMDBMatch, log: EventWriter,
                   *, movie: CatalogueMovie | None = None) -> None:
        if result.catalogue_saved:
            if not result.file_moved or result.discard_files:
                self._finish_move(batch.id, item.id, result, log)
            return
        response = result.resolved_response
        if (result.skipped or result.error is not None
                or result.selection_pending or result.selection_error is not None
                or response is None or response['total_results'] != 1):
            return
        try:
            movie_id = response['results'][0]['id']
            preferred, discarded = ((item.path, []) if item.find_ls is not None or result.replace_local_media else
                                    MovieFormats.choose(item.path, self._workspace.catalogue_paths(movie_id)))
            discard_files = CatalogueFiles.discard_snapshot(discarded)
            if item.path in discarded:
                result = replace(result, catalogue_saved=True, catalogue_error=None, duplicate=True,
                                 source_path=item.path, catalogue_path=preferred, discard_files=discard_files,
                                 source_directory=item.source_directory)
                self._workspace.save_match(batch.id, item.id, result, None)
                self._finish_move(batch.id, item.id, result, log)
                return
            if movie is None:
                movie = TMDBCatalogue(TMDB.from_environment()).movie(movie_id)
            moved_files = []
            if item.find_ls is not None or item.source_directory is not None:
                files, moved_files = DirectoryMediaMove().prepare(movie, item, batch.destination_directory, log,
                                                          replace_existing=result.replace_local_media)
            else:
                files = CatalogueFiles().prepare(movie, item.path, batch.destination_directory, item.id, log,
                                                **({'replace_existing': True} if result.replace_local_media else {}))
        except (TMDBError, OSError, ValueError, httpx.HTTPError) as error:
            self._catalogue_failure(batch.id, item.id, result, error, log)
            return
        result = replace(result, catalogue_saved=True, catalogue_error=None,
                         source_path=item.path, catalogue_path=files.video, discard_files=discard_files,
                         moved_files=moved_files, source_directory=item.source_directory,
                         preserve_source_directory=any(issue.code == 'unresolved_srt' for issue in item.issues))
        self._workspace.save_catalogue(batch.id, item.id, movie, result, log.prepare(
            Categories.DB.CREATE_RECORD, Names.DB_CREATE_RECORD,
            {'movie_id': movie.tmdb_id, 'title': movie.title, 'path': files.video,
             'outcome': 'saved', 'associated_files': files.associated}, source='CatalogueDb'), files)
        self._finish_move(batch.id, item.id, result, log)

    def _finish_move(self, batch_id: str, file_id: str, result: TMDBMatch, log: EventWriter) -> None:
        try:
            if result.moved_files:
                SourceDirectoryCleanup().finish(result.source_directory or result.source_path, result.moved_files,
                                                preserve_directory=result.source_directory is not None
                                                or result.preserve_source_directory)
                log.write(Categories.File.DELETE, Names.FILE_DELETE,
                          {'outcome': 'deleted', 'paths': [move['source'] for move in result.moved_files],
                           'source_directory': result.source_directory or result.source_path,
                           'directory_preserved': result.source_directory is not None or result.preserve_source_directory,
                           'error': None}, source='SourceDirectoryCleanup')
                for move in result.moved_files:
                    CatalogueFiles().finish(move['source'], move['destination'], move['stage_id'], preserve_source=True)
                    log.write(Categories.File.MOVE, Names.FILE_MOVE,
                              {'source_path': move['source'], 'destination_path': move['destination'],
                               'outcome': 'moved', 'error': None}, source='CatalogueFiles')
            elif not result.duplicate:
                CatalogueFiles().finish(result.source_path, result.catalogue_path, file_id)
            self._cleanup_directory(result, log)
        except (OSError, ValueError) as error:
            result = replace(result, catalogue_error=str(error))
        else:
            result = replace(result, file_moved=True, catalogue_error=None)
        if not result.duplicate:
            self._workspace.save_match(batch_id, file_id, result, log.prepare(
                Categories.File.MOVE, Names.FILE_MOVE,
                {'outcome': 'failed' if result.catalogue_error else 'moved',
                 'source_path': result.source_path, 'destination_path': result.catalogue_path,
                 'error': result.catalogue_error}, source='CatalogueFiles',
                level='ERROR' if result.catalogue_error else 'INFO'))
        if result.catalogue_error is not None or not result.discard_files:
            return
        try:
            CatalogueFiles().discard(result.discard_files, result.catalogue_path)
            self._cleanup_directory(result, log)
        except (OSError, ValueError) as error:
            result = replace(result, file_moved=False, catalogue_error=str(error))
        event = log.prepare(Categories.File.DELETE, Names.FILE_DELETE,
                            {'outcome': 'failed' if result.catalogue_error else 'deleted',
                             'paths': [item['path'] for item in result.discard_files],
                             'preferred_path': result.catalogue_path, 'error': result.catalogue_error},
                            source='CatalogueFiles', level='ERROR' if result.catalogue_error else 'INFO')
        if result.catalogue_error:
            self._workspace.save_match(batch_id, file_id, result, event)
        else:
            self._workspace.finish_duplicates(batch_id, file_id, result, event)

    @staticmethod
    def _cleanup_directory(result: TMDBMatch, log: EventWriter) -> None:
        if result.source_directory is not None and DirectoryFiles().remove_without_media(result.source_directory):
            log.write(Categories.File.DELETE, Names.FILE_DELETE,
                      {'outcome': 'deleted', 'paths': [], 'source_directory': result.source_directory,
                       'directory_preserved': False, 'error': None}, source='SourceDirectoryCleanup')

    def _catalogue_failure(self, batch_id: str, file_id: str, result: TMDBMatch,
                           error: Exception, log: EventWriter) -> None:
        result = replace(result, catalogue_error=str(error))
        self._workspace.save_match(batch_id, file_id, result, log.prepare(
            Categories.TMDB.RESULT, Names.TMDB_RESULT, dict(asdict(result), outcome=result.label),
            source='Catalogue', level='ERROR'))

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
