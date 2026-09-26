"""Resolve episode artifacts using a previously confirmed TMDB series."""

import asyncio
from dataclasses import replace

from r3el.activity.EventWriter import EventWriter
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.app.ToolConversation import ToolConversation
from r3el.constants.DEventCategory import DEventCategory as Categories
from r3el.constants.DEventName import DEventName as Names
from r3el.interface.EventLogDb import EventLogDb
from r3el.interface.LLM import LLM
from r3el.zmq.ZMQServer import ZMQServer


class TVEpisodeMapping:
    def __init__(self, workspace, llm=None):
        self.workspace, self.llm = workspace, llm

    def run(self, batch, item, result, log):
        if result.episodes_mapped or result.file_moved:
            return result
        self.workspace.check_stop(batch.id)
        series = result.resolved_response['results'][0]
        confirmed = {'tmdb_id': series['id'], 'name': series['name'],
                     'first_air_date': series.get('first_air_date'), 'overview': series.get('overview')}
        log = EventWriter(log.record, {**log.context, 'media_type': 'tv', 'phase': 'tv_episodes',
                                      'confirmed_series': confirmed}, log.parent_event_id)
        handler = SubmissionHandler(EventLogDb.record_separately)
        with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
            mapped = asyncio.run(ToolConversation(self.llm or LLM.from_environment(), listener.endpoint,
                handler, log, directory={**item.directory_context, 'confirmed_series': confirmed}).run())
        self.workspace.check_stop(batch.id)
        if mapped['status'] == 'identified':
            item.assign_episodes(mapped['episodes'])
            result = replace(result, episodes_mapped=True, catalogue_error=None)
            item.tmdb_match = result
            self.workspace.save_file(batch.id, item, log.prepare(
                Categories.Batch.BATCH_IDENTIFICATION, Names.ITEM_COMPLETED,
                {'phase': 'tv_episodes', 'count': len(mapped['episodes'])}, source='TVEpisodeMapping'))
            return result
        error = 'Episode mapping unresolved: ' + mapped['reason']
        result = replace(result, episodes_mapped=False, catalogue_error=error)
        self.workspace.save_match(batch.id, item.id, result, log.prepare(
            Categories.TMDB.RESULT, Names.TMDB_RESULT,
            {'outcome': 'Episode mapping unresolved', 'error': error},
            source='TVEpisodeMapping', level='ERROR'))
        return result
