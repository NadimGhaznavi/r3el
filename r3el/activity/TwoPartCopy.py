"""Prepare the ordered videos and associated subtitles as one catalogue result."""

from r3el.activity.EventWriter import EventWriter
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.entity.CatalogueMovie import CatalogueMovie
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MovieFiles import MovieFiles
from r3el.interface.CatalogueFiles import CatalogueFiles


class TwoPartCopy:
    def prepare(self, movie: CatalogueMovie, item: MediaFile, destination: str | None,
                log: EventWriter, *, replace_existing: bool = False) -> tuple[MovieFiles, list[dict]]:
        associated, copies = [], []
        poster = backdrop = video = None
        for position, attachment in enumerate(item.attachments):
            if attachment.kind == 'subtitle' and attachment.media_path is None:
                continue
            stage_id = f'{item.id}-{position}'
            data = {'source_path': attachment.path, 'part': attachment.part, 'kind': attachment.kind}
            log.write(Categories.File.MOVE, Names.FILE_COPY, {**data, 'outcome': 'started'}, source='TwoPartCopy')
            try:
                prepared = CatalogueFiles().prepare(movie, attachment.path, destination, stage_id, log,
                                                    part=attachment.part, copy=True, replace_existing=replace_existing)
            except (OSError, ValueError) as error:
                log.write(Categories.File.MOVE, Names.FILE_COPY,
                          {**data, 'outcome': 'failed', 'error': str(error)}, source='TwoPartCopy', level='ERROR')
                raise
            associated.append({'path': prepared.video, 'part': attachment.part, 'kind': attachment.kind})
            copies.append({'source': attachment.path, 'destination': prepared.video, 'stage_id': stage_id})
            if attachment.kind == 'video' and attachment.part == 1:
                video = prepared.video
            poster, backdrop = prepared.poster, prepared.backdrop
            log.write(Categories.File.MOVE, Names.FILE_COPY,
                      {**data, 'destination_path': prepared.video, 'outcome': 'prepared'}, source='TwoPartCopy')
        return MovieFiles(video, poster, backdrop, associated), copies
