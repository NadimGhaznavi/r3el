"""Import each validated TV episode with an independent durable checkpoint."""

from dataclasses import replace
from pathlib import Path
import httpx

from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.DirectoryFiles import DirectoryFiles
from r3el.interface.SourceDirectoryCleanup import SourceDirectoryCleanup
from r3el.interface.TMDB import TMDB, TMDBError
from r3el.interface.TVCatalogue import TVCatalogue


class TVImport:
    def __init__(self, workspace):
        self.workspace = workspace

    def run(self, batch, item, result, log):
        if result.file_moved:
            return
        errors = []
        client = TMDB.from_environment()
        try:
            series = TVCatalogue.series(client.tv_details(result.resolved_response['results'][0]['id']))
            if series.release_date is None:
                raise TMDBError('A series first-air date is required for naming.')
        except (TMDBError, ValueError) as error:
            self._finish(batch, item, result, log, [str(error)])
            return
        destination = batch.tv_destination_directory
        if not destination and batch.destination_directory:
            destination = str(Path(batch.destination_directory).parent / 'tv')
        seasons = {}
        for position, video in enumerate(item.attachments):
            if video.kind != 'video':
                continue
            self.workspace.check_stop(batch.id)
            checkpoint = video.import_result or {}
            if checkpoint.get('moved'):
                continue
            data = {'source_path': video.path, 'destination_path': destination, 'error': None,
                    'season': video.season_number, 'episode': video.episode_number}
            log.write(Categories.File.MOVE, Names.FILE_MOVE, dict(data, outcome='started'), source='TVImport')
            try:
                if not checkpoint.get('catalogue_saved'):
                    season_number, episode_number = video.season_number, video.episode_number
                    if season_number is None or episode_number is None:
                        raise ValueError('Episode season/number is unresolved.')
                    if season_number not in seasons:
                        seasons[season_number] = TVCatalogue.season(client.tv_season(series.tmdb_id, season_number), season_number)
                    season = seasons[season_number]
                    if not any(row.get('episode_number') == episode_number for row in season['episodes']):
                        raise ValueError(f'TMDB does not contain S{season_number:02}E{episode_number:02}.')
                    episode = TVCatalogue.episode(client.tv_episode(series.tmdb_id, season_number, episode_number),
                                                  season_number, episode_number)
                    files, artwork = [], []
                    for attachment_position, attachment in enumerate(item.attachments):
                        if attachment is not video and not (
                                attachment.kind == 'subtitle' and attachment.media_path == video.path):
                            continue
                        stage_id = f'{item.id}-{attachment_position}'
                        prepared = CatalogueFiles().prepare(
                            series, attachment.path, destination, stage_id, log,
                            season=season_number, episode=episode_number, episode_title=episode['name'],
                            replace_existing=result.replace_local_media)
                        files.append({'source': attachment.path, 'destination': prepared.video,
                                      'stage_id': stage_id, 'kind': attachment.kind})
                        for kind, path in (('poster', prepared.poster), ('backdrop', prepared.backdrop)):
                            if path and not any(art['path'] == path for art in artwork):
                                artwork.append({'kind': kind, 'path': path})
                    folder = Path(files[0]['destination']).parent
                    for remote, kind, extra in (
                        (season.get('poster_path'), 'poster', {'season_number': season_number}),
                        (episode.get('still_path'), 'still', {'episode_id': episode['id']})):
                        path = CatalogueFiles().artwork(remote, folder, kind, log)
                        if path:
                            artwork.append(dict(extra, kind=kind, path=path))
                    checkpoint = {'catalogue_saved': True, 'moved': False, 'files': files}
                    self.workspace.save_tv_episode(batch.id, item, position, checkpoint, log.prepare(
                        Categories.DB.CREATE_RECORD, Names.DB_CREATE_RECORD,
                        {'movie_id': series.tmdb_id, 'title': series.title, 'path': files[0]['destination'],
                         'episode_id': episode['id'], 'outcome': 'saved'}, source='TVCatalogueDb'),
                        series=series, season=season, episode=episode, artwork=artwork)
                SourceDirectoryCleanup().finish(item.source_directory, checkpoint['files'], preserve_directory=True)
                for file in checkpoint['files']:
                    CatalogueFiles().finish(file['source'], file['destination'], file['stage_id'], preserve_source=True)
                checkpoint = dict(checkpoint, moved=True, error=None)
                self.workspace.save_tv_episode(batch.id, item, position, checkpoint, log.prepare(
                    Categories.File.MOVE, Names.FILE_MOVE,
                    dict(data, destination_path=checkpoint['files'][0]['destination'], outcome='moved'),
                    source='TVImport'))
            except (OSError, ValueError, TMDBError, httpx.HTTPError) as error:
                errors.append(str(error))
                checkpoint = dict(checkpoint, error=str(error))
                self.workspace.save_tv_episode(batch.id, item, position, checkpoint, log.prepare(
                    Categories.File.MOVE, Names.FILE_MOVE, dict(data, outcome='failed', error=str(error)),
                    source='TVImport', level='ERROR'))
        if DirectoryFiles().remove_without_media(item.source_directory):
            log.write(Categories.File.DELETE, Names.FILE_DELETE,
                      {'outcome': 'deleted', 'paths': [], 'source_directory': item.source_directory,
                       'directory_preserved': False, 'error': None}, source='TVImport')
        self._finish(batch, item, result, log, errors)

    def _finish(self, batch, item, result, log, errors):
        result = replace(result, catalogue_saved=not errors, file_moved=not errors,
                         catalogue_error=errors[0] if errors else None, media_type='tv')
        self.workspace.save_match(batch.id, item.id, result, log.prepare(
            Categories.TMDB.RESULT, Names.TMDB_RESULT,
            {'outcome': result.label, 'error': result.catalogue_error}, source='TVImport'))
