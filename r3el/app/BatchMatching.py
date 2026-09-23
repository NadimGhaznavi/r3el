"""Match approved identifications and checkpoint downloaded TMDB results."""

from r3el.activity.BatchPreparation import BatchPreparation
from r3el.entity.MediaFileAction import MediaFileAction
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.WorkspaceDb import WorkspaceDb, WorkspaceActionConflict


class BatchMatching:
    def __init__(self, workspace: WorkspaceDb) -> None:
        self._workspace = workspace

    def run(self, batch_id: str) -> None:
        with self._workspace.processing(), self._workspace.matching():
            batch = self._workspace.load()
            if batch is None or batch.id != batch_id or not BatchPreparation.ready(batch):
                raise WorkspaceActionConflict('Resolve every file action after identification finishes.')
            client = None
            for item in batch.files:
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
                        result = TMDBMatch(title, year, response=client.search(title, year))
                    except TMDBError as error:
                        result = TMDBMatch(title, year, error=str(error))
                self._workspace.save_match(batch.id, item.id, result)
