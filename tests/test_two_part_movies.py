"""Directory detection, part validation, paired copying, and sequential orchestration."""

from contextlib import nullcontext
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, Mock, patch

from r3el.activity.DirectoryDiscovery import DirectoryDiscovery
from r3el.activity.EventWriter import EventWriter
from r3el.activity.TwoPartCopy import TwoPartCopy
from r3el.app.BatchRunner import BatchRunner
from r3el.app.SubmissionHandler import SubmissionHandler
from r3el.app.ToolConversation import ToolConversation
from r3el.entity.BatchRequest import BatchRequest
from r3el.entity.MediaAttachment import MediaAttachment
from r3el.entity.MediaFile import MediaFile, MediaFileState
from r3el.entity.MediaFileBatch import MediaFileBatch, MediaFileBatchState
from r3el.interface.CatalogueFiles import CatalogueFiles
from r3el.interface.DirectoryFiles import DirectoryFiles
from r3el.interface.TMDBCatalogue import TMDBCatalogue
from r3el.zmq.ZMQMsg import ZMQMsg
from test_catalogue import movie_payload


class DirectoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.batch = MediaFileBatch('batch', 5, str(self.root))
        self.events = []
        self.log = EventWriter(lambda event: self.events.append(event) or len(self.events), {'batch_id': 'batch'}, 1)
        self.workspace = Mock()
        def append(batch, items, event):
            batch.files.extend(items)
            batch.directories_scanned = True
            self.events.append(event)
        self.workspace.append_directories.side_effect = append

    def file(self, name, size=100 * 1024 * 1024 + 1):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('wb') as stream:
            stream.truncate(size)
        return str(path)

    def test_recursive_detection_threshold_supported_formats_and_no_duplicate_parent(self):
        a = self.file('parent/movie/a.AVI')
        b = self.file('parent/movie/b.mkv')
        self.file('parent/movie/sample.mp4', 100 * 1024 * 1024)
        self.file('parent/movie/large.bin')
        self.file('parent/movie/a.srt', 10)
        self.file('parent/movie/unknown.srt', 10)
        for name in ('a.avi', 'b.avi', 'c.avi'):
            self.file('three/' + name)
        self.file('one/a.mkv')
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        self.assertEqual(len(self.batch.files), 1)
        item = self.batch.files[0]
        self.assertEqual(item.path, str(self.root / 'parent/movie'))
        self.assertEqual([a.path for a in item.attachments if a.kind == 'video'], [b, a])
        self.assertIn('a.AVI', item.find_ls)
        self.assertEqual([issue.code for issue in item.issues], ['unresolved_srt'])
        item.assign_parts(a, b)
        self.assertEqual([(Path(f.path).name, f.part) for f in item.attachments if f.kind == 'subtitle'],
                         [('a.srt', 1), ('unknown.srt', None)])
        events = [json.loads(event.message)['data'] for event in self.events
                  if event.name == 'subtitle_association']
        self.assertEqual([event['outcome'] for event in events], ['associated', 'unresolved_srt'])
        self.workspace.append_directories.reset_mock()
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        self.workspace.append_directories.assert_not_called()

    def test_cd_folders_pair_different_basenames_and_copy_srt_with_assigned_part(self):
        a = self.file('Under.Capricorn/CD1/nogrp-uc-cd1.avi')
        b = self.file('Under.Capricorn/CD2/nogrp-uc-cd2.avi')
        first = self.file('Under.Capricorn/CD1/Under Capricorn (1949) CD1.srt', 10)
        second = self.file('Under.Capricorn/CD2/Under Capricorn (1949) CD2.srt', 10)
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        self.assertEqual(len(self.batch.files), 1)
        item = self.batch.files[0]
        self.assertEqual(item.issues, [])
        subtitles = [file for file in item.attachments if file.kind == 'subtitle']
        self.assertEqual([(file.path, file.media_path) for file in subtitles], [(first, a), (second, b)])
        item.assign_parts(b, a)
        # Use small fixtures for the copy itself; discovery already verified the size threshold.
        Path(a).write_bytes(b'video a')
        Path(b).write_bytes(b'video b')
        movie = replace(TMDBCatalogue.from_details(movie_payload(), 42), poster_path=None, backdrop_path=None)
        files, _ = TwoPartCopy().prepare(movie, item, str(self.root / 'output'), self.log)
        copied = [file for file in files.associated if file['kind'] == 'subtitle']
        self.assertEqual([Path(file['path']).name for file in copied],
                         ['Movie (2020) Part 2.srt', 'Movie (2020) Part 1.srt'])
        self.assertEqual([Path(file['path']).read_bytes() for file in copied],
                         [Path(first).read_bytes(), Path(second).read_bytes()])

    def test_different_subtitle_name_with_two_sibling_videos_remains_unresolved(self):
        self.file('movie/a.avi')
        self.file('movie/b.avi')
        self.file('movie/subtitle.srt', 10)
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        item = self.batch.files[0]
        self.assertEqual([issue.code for issue in item.issues], ['unresolved_srt'])
        self.assertIsNone(item.attachments[-1].media_path)

    def test_find_handles_spaces_newlines_and_symlinks_without_following(self):
        name = 'movie/a weird\nname.avi'
        path = self.file(name)
        (self.root / 'movie/link.avi').symlink_to(path)
        listing, files = DirectoryFiles().scan(self.root / 'movie')
        self.assertEqual(files, [(path, 100 * 1024 * 1024 + 1)])
        self.assertIn('link.avi', listing)

    def test_ambiguous_subtitles_are_unresolved_instead_of_competing_for_one_destination(self):
        self.file('movie/a.avi')
        self.file('movie/b.avi')
        self.file('movie/a.srt', 10)
        self.file('movie/subs/a.srt', 10)
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        item = self.batch.files[0]
        subtitles = [file for file in item.attachments if file.kind == 'subtitle']
        self.assertEqual([file.media_path for file in subtitles], [None, None])
        self.assertEqual([issue.code for issue in item.issues], ['unresolved_srt', 'unresolved_srt'])

    def test_output_subtree_is_excluded_from_parent_listing_and_detection(self):
        self.file('movie/a.avi')
        self.file('movie/b.avi')
        self.file('movie/output/existing.mkv')
        self.batch.destination_directory = str(self.root / 'movie/output')
        DirectoryDiscovery().run(self.batch, self.workspace, self.log)
        self.assertEqual(len(self.batch.files), 1)
        self.assertNotIn('existing.mkv', self.batch.files[0].find_ls)


class PartSubmissionTests(unittest.TestCase):
    def test_rejects_duplicate_unknown_and_missing_parts_but_accepts_swapped_order(self):
        handler = SubmissionHandler(Mock(return_value=1))
        handler.register({'batch_id': 'batch', 'attempt_id': 'attempt', 'media_files': ['/a.avi', '/b.avi']}, 1)
        good = {'title': 'Movie', 'year': 1949, 'confidence': 10, 'part_one': '/b.avi', 'part_two': '/a.avi'}
        def submit(data):
            return handler.handle(ZMQMsg(sender='test', target='identification', method='submit_identification',
                payload={'attempt_id': 'attempt', 'submission': data}))
        result = submit(good)
        self.assertEqual(result['parts'], {'part_one': '/b.avi', 'part_two': '/a.avi'})
        for change in ({'part_one': '/a.avi'}, {'part_two': '/outside.avi'}, {'part_one': []}, {'confidence': 11}):
            self.assertEqual(submit(dict(good, **change))['status'], 'rejected')
        self.assertEqual(submit({k: v for k, v in good.items() if k != 'part_one'})['status'], 'rejected')
        body = json.dumps({'choices': [{'message': {'tool_calls': [
            {'id': 'call', 'function': {'name': 'submit_two_parts', 'arguments': json.dumps(good)}}]}}]})
        self.assertEqual(ToolConversation._tool_call(body, two_parts=True)[2], good)
        with self.assertRaises(ValueError):
            ToolConversation._tool_call(body)


class CopyTests(unittest.TestCase):
    def test_copies_paired_names_preserves_sources_skips_unresolved_and_resumes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            attachments = []
            for name in ('a.avi', 'a.srt', 'b.avi', 'b.srt', 'unknown.srt'):
                path = root / name
                path.write_bytes(name.encode())
                attachments.append(MediaAttachment(str(path), 'subtitle' if name.endswith('.srt') else 'video',
                    media_path=str(root / (name[0] + '.avi')) if name in ('a.srt', 'b.srt') else None))
            item = MediaFile('item', str(root), find_ls='listing', attachments=attachments)
            item.assign_parts(str(root / 'b.avi'), str(root / 'a.avi'))
            movie = replace(TMDBCatalogue.from_details(movie_payload(), 42), title='Under Capricorn',
                            poster_path=None, backdrop_path=None)
            log = EventWriter(Mock(return_value=1), {'batch_id': 'batch', 'item_id': 'item'})
            output = str(root / 'output')
            files, copies = TwoPartCopy().prepare(movie, item, output, log)
            self.assertEqual(len(files.associated), 4)
            self.assertEqual(TwoPartCopy().prepare(movie, item, output, log), (files, copies))
            for copy in copies:
                target = Path(copy['destination'])
                part = 1 if Path(copy['source']).stem == 'b' else 2
                self.assertEqual(target.name, f'Under Capricorn (2020) Part {part}{target.suffix}')
                self.assertEqual(target.read_bytes(), Path(copy['source']).read_bytes())
                self.assertFalse(target.samefile(copy['source']))
                CatalogueFiles().finish(copy['source'], copy['destination'], copy['stage_id'], preserve_source=True)
                CatalogueFiles().finish(copy['source'], copy['destination'], copy['stage_id'], preserve_source=True)
                self.assertTrue(Path(copy['source']).exists())
            self.assertTrue((root / 'unknown.srt').exists())
            self.assertFalse(list((root / 'output').rglob('unknown.srt')))
            self.assertFalse(list((root / 'output').rglob('.r3el-*')))
            with self.assertRaises(FileExistsError):
                TwoPartCopy().prepare(movie, item, output, log)


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_files_then_each_directory_and_only_then_batch_completion(self):
        with TemporaryDirectory() as directory, patch('r3el.app.BatchRunner.DbMgr'), \
                patch('r3el.app.BatchRunner.WorkspaceDb') as workspaces, \
                patch('r3el.app.BatchRunner.EventLogDb') as events, \
                patch('r3el.app.BatchRunner.BatchIdentification') as identification, \
                patch('r3el.app.BatchRunner.BatchMatching') as matching, \
                patch('r3el.app.BatchRunner.DirectoryDiscovery') as discovery:
            batch = MediaFileBatch('batch', 5, directory, files=[MediaFile('ordinary', '/a.mkv')],
                                   state=MediaFileBatchState.MATCHING)
            workspace = workspaces.return_value
            workspace.load.return_value = batch
            workspace.processing.side_effect = nullcontext
            events.return_value.record.return_value = 1
            order = []
            async def identify(*args, **kwargs):
                group = batch.files[kwargs['offset']:kwargs['offset'] + kwargs['limit']]
                for item in group:
                    order.append(('identify', item.id))
                    item.state = MediaFileState.IDENTIFIED
            identification.return_value.run = AsyncMock(side_effect=identify)
            matching.return_value.run.side_effect = lambda batch_id, file_ids: order.append(('match', file_ids[0]))
            def scan(batch, workspace, log):
                order.append(('scan', None))
                batch.files.extend([MediaFile('directory1', '/d1', find_ls='listing'),
                                    MediaFile('directory2', '/d2', find_ls='listing')])
                batch.directories_scanned = True
            discovery.return_value.run.side_effect = scan
            await BatchRunner('http://model', 'endpoint', Mock()).run(BatchRequest(directory, '/out', 5))
            self.assertEqual(order, [('identify', 'ordinary'), ('match', 'ordinary'), ('scan', None),
                                     ('identify', 'directory1'), ('match', 'directory1'),
                                     ('identify', 'directory2'), ('match', 'directory2')])
            self.assertEqual(workspace.save_batch_state.call_args.args[1], MediaFileBatchState.MATCHING_COMPLETED)


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_directory_prompt_and_part_order_cross_real_mcp_and_zmq(self):
        from r3el.zmq.ZMQServer import ZMQServer
        record = Mock(return_value=1)
        handler = SubmissionHandler(record)
        submission = {'title': 'Movie', 'year': 1949, 'confidence': 9,
                      'part_one': '/b.avi', 'part_two': '/a.avi'}
        llm = Mock()
        llm.complete = AsyncMock(return_value=json.dumps({'choices': [{'message': {'tool_calls': [
            {'id': 'parts', 'type': 'function', 'function': {'name': 'submit_two_parts',
                                                          'arguments': json.dumps(submission)}}]}}]}))
        context = {'find-ls': 'directory listing', 'media_file_a': '/a.avi', 'media_file_b': '/b.avi'}
        with ZMQServer('tcp://127.0.0.1:*', handler.handle) as listener:
            result = await ToolConversation(llm, listener.endpoint, handler,
                EventWriter(record, {'batch_id': 'batch', 'item_id': 'item', 'filename': 'directory'}),
                directory=context).run()
        self.assertEqual(result['parts'], {'part_one': '/b.avi', 'part_two': '/a.avi'})
        self.assertEqual(result['identification'], {'title': 'Movie', 'year': 1949, 'confidence': 9})
        payload = llm.complete.call_args.args[0]
        self.assertEqual(payload['tools'][0]['function']['name'], 'submit_two_parts')
        self.assertIn(context, [json.loads(message['content'])['data'] for message in payload['messages']
                                if message.get('content', '').startswith('{')])
