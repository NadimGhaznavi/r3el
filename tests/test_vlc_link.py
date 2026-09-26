"""Verify local VLC link decoding, launch arguments, and desktop registration."""

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('vlc_link', Path(__file__).parents[1] / 'scripts/vlc-link.py')
vlc_link = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlc_link)


class VLCLinkTests(unittest.TestCase):
    def test_encoded_filename_round_trip(self):
        self.assertEqual(vlc_link.media_path('r3el-vlc:///imports/Film%20%26%20%22%C3%A9%22%20%231%25.mkv'),
                         '/imports/Film & "é" #1%.mkv')
        self.assertEqual(vlc_link.media_path('r3el-vlc:///imports/%2520.mkv'), '/imports/%20.mkv')

    def test_rejects_remote_urls_and_non_paths(self):
        for url in ('https://example.com/movie', 'r3el-vlc://host/movie',
                    'r3el-vlc:--option', 'r3el-vlc:///imports/a?option=value',
                    'r3el-vlc:///imports/a#fragment', 'r3el-vlc:///imports/%00',
                    'r3el-vlc:////host/movie'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                vlc_link.media_path(url)

    def test_launch_passes_filename_as_one_argument_without_shell(self):
        with TemporaryDirectory() as directory:
            media = Path(directory) / 'Movie $(test) #1.mkv'
            media.touch()
            url = media.as_uri().replace('file:', 'r3el-vlc:', 1)
            with patch('sys.argv', ['vlc-link.py', url]), patch.object(vlc_link.subprocess, 'run') as run:
                vlc_link.main()
            run.assert_called_once_with(['vlc', '--', str(media)], check=True)

    def test_install_registers_copied_handler(self):
        with TemporaryDirectory() as directory:
            with patch.dict('os.environ', {'XDG_DATA_HOME': directory}), \
                    patch.object(vlc_link.shutil, 'which', return_value='/usr/bin/tool'), \
                    patch.object(vlc_link.subprocess, 'run') as run:
                vlc_link.install()
            self.assertEqual((Path(directory) / 'r3el/vlc-link.py').read_bytes(),
                             Path(vlc_link.__file__).read_bytes())
            entry = (Path(directory) / 'applications/r3el-vlc.desktop').read_text()
            self.assertIn('MimeType=x-scheme-handler/r3el-vlc;', entry)
            self.assertIn(' %u\n', entry)
            run.assert_called_once_with(['xdg-mime', 'default', 'r3el-vlc.desktop',
                                         'x-scheme-handler/r3el-vlc'], check=True)
