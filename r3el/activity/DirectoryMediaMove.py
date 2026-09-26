"""Prepare directory media and associated subtitles as one catalogue result."""

from r3el.activity.EventWriter import EventWriter
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.CatalogueFiles import CatalogueFiles


class DirectoryMediaMove:
    def prepare(self, movie: CatalogueMovie, item: MediaFile, destination: str | None,
                log: EventWriter, *, replace_existing: bool = False) -> tuple[MovieFiles, list[dict]]:
        associated, moves = [], []
        poster = backdrop = video = None
        for position, attachment in enumerate(item.attachments):
            if attachment.kind == 'subtitle' and attachment.media_path is None:
                continue
            stage_id = f'{item.id}-{position}'
            data = {'source_path': attachment.path, 'part': attachment.part, 'kind': attachment.kind,
                    'destination_path': destination, 'error': None}
            log.write(Categories.File.MOVE, Names.FILE_MOVE, {**data, 'outcome': 'started'}, source='DirectoryMediaMove')
            try:
                prepared = CatalogueFiles().prepare(movie, attachment.path, destination, stage_id, log,
                                                    part=attachment.part, replace_existing=replace_existing)
            except (OSError, ValueError) as error:
                log.write(Categories.File.MOVE, Names.FILE_MOVE,
                          {**data, 'outcome': 'failed', 'error': str(error)}, source='DirectoryMediaMove', level='ERROR')
                raise
            associated.append({'path': prepared.video, 'part': attachment.part, 'kind': attachment.kind})
            moves.append({'source': attachment.path, 'destination': prepared.video, 'stage_id': stage_id})
            if attachment.kind == 'video' and attachment.part in (None, 1):
                video = prepared.video
            poster, backdrop = prepared.poster, prepared.backdrop
            log.write(Categories.File.MOVE, Names.FILE_MOVE,
                      {**data, 'destination_path': prepared.video, 'outcome': 'prepared'}, source='DirectoryMediaMove')
        return MovieFiles(video, poster, backdrop, associated), moves
