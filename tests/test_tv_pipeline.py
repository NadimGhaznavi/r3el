"""TV discovery, constrained episode mapping and metadata-only imports."""

from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from r3el.activity.TVPattern import TVPattern
from r3el.activity.DirectoryDiscovery import DirectoryDiscovery
from r3el.activity.EventWriter import EventWriter
from r3el.app.TVImport import TVImport
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile
from r3el.entity.MediaFileBatch import MediaFileBatch
from r3el.entity.TMDBMatch import TMDBMatch
from r3el.app.ToolConversation import ToolConversation
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.constants.DMessage import DMessage
from r3el.zmq.ZMQMsg import ZMQMsg


class TVPatternTests(unittest.TestCase):
    def test_three_directory_shapes(self):
        paths = [f'/film/11.22.63/11.22.63-{n:02}.mkv' for n in range(1, 9)]
        result = TVPattern.match(paths)
        self.assertEqual(result[paths[0]], dict(season_number=None, episode_number=1))
        self.assertEqual(len(result), 8)
        path = '/film/12-Monkeys/12-Monkeys-S01E01.mkv'
        self.assertEqual(TVPattern.match([path])[path], dict(season_number=1, episode_number=1))
        paths = [f'/film/Slow-Horses/season-{s}/Slow-Horse-S{s:02}E{e:02}.mkv'
                 for s in range(1, 6) for e in range(1, 7)]
        self.assertEqual(len(TVPattern.match(paths)), 30)

    def test_not_movie_parts_or_dated_movies(self):
        for paths in (['Movie CD1.avi', 'Movie CD2.avi'],
                      ['Movie-Part-1.avi', 'Movie-Part-2.avi'],
                      ['Alice-2010.avi', 'Alice-2016.avi'],
                      ['Show-S01E01E02.mkv'], ['Show-S01E01-02.mkv']):
            self.assertIsNone(TVPattern.match(paths), paths)

    def test_two_episodes_take_priority_and_directory_counts_once(self):
        paths = ['/film/Show/Show-S01E01.mkv', '/film/Show/Show-S01E02.mkv']
        filesystem = Mock()
        filesystem.directories.return_value = [Path('/film/Show')]
        filesystem.scan.return_value = ('listing', [(p, 101*1024*1024) for p in paths])
        workspace = Mock()
        batch = MediaFileBatch('batch', 1, '/film', destination_directory='/media/movies')
        with patch('r3el.activity.DirectoryDiscovery.DirectoryFiles', return_value=filesystem):
            DirectoryDiscovery().run(batch, workspace, EventWriter(Mock(return_value=1), {'batch_id': 'batch'}))
        items = workspace.append_directories.call_args.args[1]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].media_type, 'tv')
        self.assertEqual(len(items[0].attachments), 2)

    def test_mapping_cannot_override_explicit_numbers_or_duplicate_episodes(self):
        expected = {'one': dict(season_number=2, episode_number=1),
                    'two': dict(season_number=None, episode_number=2)}
        rows = [dict(path=p, season_number=2, episode_number=i) for i,p in enumerate(expected,1)]
        self.assertEqual(TVPattern.validate(rows, expected), rows)
        rows[0]['season_number'] = 1
        with self.assertRaises(ValueError):
            TVPattern.validate(rows, expected)
        rows[0]['season_number'] = 2
        rows[1]['path'] = 'one'
        with self.assertRaises(ValueError):
            TVPattern.validate(rows, expected)

    def test_tv_submission_validation(self):
        record = Mock(return_value=1)
        handler = SubmissionHandler(record)
        handler.register({'attempt_id': 'a', 'batch_id': 'b', 'tv_episodes': {
            '/show-01.mkv': dict(season_number=None, episode_number=1)}}, 1)
        submission = dict(title='Show', year=2020, confidence=9,
                          episodes=[dict(path='/show-01.mkv', season_number=1, episode_number=1)])
        request = ZMQMsg(sender='test', target=DMessage.IDENTIFICATION, method=DMessage.SUBMIT_IDENTIFICATION,
                         payload={'attempt_id':'a','submission':submission})
        self.assertEqual(handler.handle(request)['episodes'], submission['episodes'])
        submission['episodes'][0]['episode_number'] = 2
        self.assertEqual(handler.handle(request)['status'], 'rejected')


class TVImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.attachments = []
        for n in (1,2):
            video = self.source / f'Show-S01E{n:02}.mkv'
            video.write_bytes(b'episode')
            self.attachments.append(MediaAttachment(str(video), season_number=1, episode_number=n))
        srt = self.source / 'Show-S01E01.srt'
        srt.write_text('subtitle')
        self.attachments.append(MediaAttachment(str(srt), kind='subtitle', media_path=self.attachments[0].path,
                                                season_number=1, episode_number=1))
        self.item = MediaFile('item',str(self.source),media_type='tv',source_directory=str(self.source),
                              find_ls='listing',attachments=self.attachments)
        self.batch = MediaFileBatch('batch',1,str(self.root),files=[self.item],
                                    destination_directory=str(self.root/'media/movies'),
                                    tv_destination_directory=str(self.root/'media/tv'))
        self.workspace = Mock()
        def save(batch_id,item,position,checkpoint,event,**kwargs):
            if kwargs:
                self.assertTrue(Path(item.attachments[position].path).exists())
            item.attachments[position].import_result = checkpoint
        self.workspace.save_tv_episode.side_effect = save
        self.log = EventWriter(Mock(return_value=1),dict(batch_id='batch',item_id='item',filename='Show'))
        self.result = TMDBMatch('Show',2020,media_type='tv',response={'total_results':1,'results':[{'id':42}]})
        self.client = Mock()
        self.client.tv_details.return_value = dict(id=42,name='Show',first_air_date='2020-01-01',
            genres=[],credits={'cast':[],'crew':[]})
        self.client.tv_season.return_value = dict(id=101,name='Season 1',season_number=1,
                                                   episodes=[{'episode_number':1},{'episode_number':2}])
        self.client.tv_episode.side_effect = lambda series,season,episode: dict(id=1000+episode,
            name=f'Episode {episode}',season_number=season,episode_number=episode,credits={'cast':[],'crew':[]})
        self.patch = patch('r3el.app.TVImport.TMDB.from_environment',return_value=self.client)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def run_import(self):
        TVImport(self.workspace).run(self.batch,self.item,self.result,self.log)

    def test_moves_episodes_and_srt_to_tv_tree_with_same_inodes(self):
        inode = Path(self.attachments[0].path).stat().st_ino
        self.run_import()
        folder = self.root/'media/tv/Show (2020)/Season 01'
        self.assertEqual((folder/'Show (2020) S01E01 - Episode 1.mkv').stat().st_ino,inode)
        self.assertEqual((folder/'Show (2020) S01E01 - Episode 1.srt').read_text(),'subtitle')
        self.assertFalse(self.source.exists())
        self.assertTrue(self.workspace.save_match.call_args.args[2].file_moved)
        self.assertFalse((self.root/'media/movies').exists())
        details = [json.loads(call.args[0].message)['data'] for call in self.log.record.call_args_list
                   if call.args[0].name == 'tmdb_details']
        self.assertEqual([(row['kind'],row['outcome'],row['episode']) for row in details], [
            ('series','started',None),('series','received',None),
            ('season','started',None),('season','received',None),
            ('episode','started',1),('episode','received',1),
            ('episode','started',2),('episode','received',2)])

    def test_missing_episode_retains_source_and_successful_episode_imports(self):
        self.client.tv_season.return_value['episodes'] = [{'episode_number':1}]
        self.run_import()
        self.assertFalse(Path(self.attachments[0].path).exists())
        self.assertTrue(Path(self.attachments[1].path).exists())
        self.assertFalse(self.workspace.save_match.call_args.args[2].file_moved)

    def test_failed_commit_preserves_source(self):
        self.workspace.save_tv_episode.side_effect = RuntimeError('database failure')
        with self.assertRaises(RuntimeError):
            self.run_import()
        self.assertTrue(all(Path(a.path).exists() for a in self.attachments))

    def test_unresolved_srt_prevents_directory_removal(self):
        (self.source/'unknown.srt').write_text('unresolved')
        self.run_import()
        self.assertTrue((self.source/'unknown.srt').exists())

    def test_mismatched_tmdb_episode_is_not_moved(self):
        self.client.tv_episode.side_effect = lambda *args: dict(
            id=123,name='Wrong episode',season_number=99,episode_number=99)
        self.run_import()
        self.assertTrue(all(Path(a.path).exists() for a in self.attachments))
        self.assertFalse(self.workspace.save_match.call_args.args[2].file_moved)
        failures = [call.args[0] for call in self.log.record.call_args_list
                    if call.args[0].name == 'tmdb_details' and call.args[0].level == 'ERROR']
        self.assertEqual(len(failures),2)
        self.assertEqual(json.loads(failures[0].message)['data']['episode'],1)

    def test_existing_episode_requires_explicit_replacement(self):
        from dataclasses import replace
        target = self.root/'media/tv/Show (2020)/Season 01/Show (2020) S01E01 - Episode 1.mkv'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'old')
        self.run_import()
        self.assertEqual(target.read_bytes(),b'old')
        self.assertTrue(Path(self.attachments[0].path).exists())
        result = self.workspace.save_match.call_args.args[2]
        self.assertTrue(result.entry_exists)
        self.result = replace(result, replace_local_media=True)
        self.run_import()
        self.assertEqual(target.read_bytes(),b'episode')
        self.assertFalse(self.source.exists())

    def test_resume_after_catalogue_commit(self):
        with patch('r3el.app.TVImport.SourceDirectoryCleanup.finish',side_effect=OSError('busy')):
            self.run_import()
        self.assertTrue(all(Path(a.path).exists() for a in self.attachments))
        self.workspace.save_tv_episode.reset_mock()
        self.client.tv_episode.reset_mock()
        self.run_import()
        self.client.tv_episode.assert_not_called()
        self.assertFalse(self.source.exists())


class TVConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_dialogue_maps_numbered_series(self):
        import json
        from unittest.mock import AsyncMock
        from r3el.zmq.ZMQServer import ZMQServer
        handler = SubmissionHandler(Mock(return_value=1))
        log = EventWriter(Mock(return_value=1),dict(batch_id='batch',item_id='item',filename='11.22.63'))
        submission = dict(title='11.22.63',year=2016,confidence=10,
                          episodes=[dict(path='/11.22.63-01.mkv',season_number=1,episode_number=1)])
        llm = Mock()
        llm.complete = AsyncMock(return_value=json.dumps({'choices':[{'message':{
            'role':'assistant','tool_calls':[{'id':'call','type':'function','function':{
                'name':'submit_tv','arguments':json.dumps(submission)}}]}}]}))
        with ZMQServer('tcp://127.0.0.1:*',handler.handle) as listener:
            result = await ToolConversation(llm,listener.endpoint,handler,log,directory={
                'find-ls':'listing','episodes':{'/11.22.63-01.mkv':{
                    'season_number':None,'episode_number':1}}}).run()
        self.assertEqual(result['status'],'identified')
        self.assertEqual(result['episodes'],submission['episodes'])
        messages = llm.complete.call_args.args[0]['messages']
        self.assertIn('first-air year',messages[1]['content'])

class TVSearchTests(unittest.TestCase):
    @patch('r3el.app.BatchMatching.TMDB.from_environment')
    def test_search_uses_tv_endpoint_and_persists_type(self, factory):
        from r3el.app.BatchMatching import BatchMatching
        log = EventWriter(Mock(return_value=1),dict(batch_id='b',item_id='i',filename='Show'))
        factory.return_value.search_tv.return_value = {'total_results':1,'results':[{'id':42,'name':'Show'}]}
        result = BatchMatching._search('Show',2020,log,media_type='tv')
        self.assertEqual(result.media_type,'tv')
        factory.return_value.search_tv.assert_called_once_with('Show',2020)
        factory.return_value.search.assert_not_called()
