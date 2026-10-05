"""Exercise releases in disposable repositories with a local bare remote."""

import json
import os
from pathlib import Path
import pty
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = 'r3el/constants/DR3el.py'


class NewReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='r3el-release-')
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name) / 'checkout'
        self.remote = Path(temporary.name) / 'origin.git'
        self.repository.mkdir()
        self.environment = dict(os.environ, GIT_CONFIG_GLOBAL='/dev/null',
                                GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0')
        self.git('init', '--initial-branch=main')
        self.git('config', 'user.name', 'Release Test')
        self.git('config', 'user.email', 'release@example.invalid')
        for name in ('scripts/new-release.sh', VERSION_FILE):
            destination = self.repository / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        self.original_metadata = (self.repository / VERSION_FILE).read_text()
        (self.repository / 'CHANGELOG.md').write_text(
            '# Changelog\n\n## [Unreleased]\n\n- Test release change.\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Initial project')
        self.git('init', '--bare', str(self.remote))
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('branch', 'dev')
        self.git('push', 'origin', 'main', 'dev')
        self.git('switch', '-c', 'feat/maint-6.8.1')
        (self.repository / 'feature.txt').write_text('Feature work\n')
        self.git('add', 'feature.txt')
        self.git('commit', '-m', 'Feature work')
        self.initial_head = self.git('rev-parse', 'HEAD')
        self.initial_main = self.git('rev-parse', 'main')

    def git(self, *arguments):
        return subprocess.run(
            ['git', *arguments], cwd=self.repository, env=self.environment,
            check=True, capture_output=True, text=True, timeout=15,
        ).stdout.strip()

    def release(self, *arguments, reply=None):
        command = ['bash', 'scripts/new-release.sh', *arguments]
        if reply is None:
            return subprocess.run(
                command, cwd=self.repository, env=self.environment,
                input='', capture_output=True, text=True, timeout=15,
            )
        master, slave = pty.openpty()
        try:
            with subprocess.Popen(
                command, cwd=self.repository, env=self.environment,
                stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True,
            ) as process:
                os.write(master, (reply + '\n').encode())
                try:
                    output, _ = process.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                    raise
                return subprocess.CompletedProcess(command, process.returncode, output)
        finally:
            os.close(master)
            os.close(slave)

    def assert_no_release(self):
        self.assertEqual(self.git('branch', '--show-current'), 'feat/maint-6.8.1')
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.initial_head)
        self.assertEqual(self.git('rev-parse', 'main'), self.initial_main)
        self.assertEqual(self.git('rev-parse', 'dev'), self.initial_main)
        self.assertEqual((self.repository / VERSION_FILE).read_text(), self.original_metadata)
        self.assertEqual(self.git('ls-remote', '--tags', 'origin'), '')

    def test_release_updates_metadata_and_publishes_matching_refs(self):
        version = '6.8.1-rc.1+build.2'
        description = 'Insight "quoted" \\ café $HOME `literal`'
        result = self.release(version, description, reply='y')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('R3el release', result.stdout)
        self.assertEqual(self.git('branch', '--show-current'), 'feat/maint-6.8.2')
        self.assertEqual(self.git('status', '--porcelain'), '')
        expected = self.original_metadata.replace('"6.8.0"', json.dumps(version)).replace(
            '"Insight"', json.dumps(description, ensure_ascii=False))
        self.assertEqual((self.repository / VERSION_FILE).read_text(), expected)
        changelog = (self.repository / 'CHANGELOG.md').read_text()
        self.assertRegex(changelog, r'## \[Unreleased\]\n\n## \[' +
                         re.escape(version) + r'\] - \d{4}-\d{2}-\d{2} @ \d{2}:\d{2}')
        self.assertTrue(changelog.endswith('\n\n- Test release change.\n'))
        head = self.git('rev-parse', 'HEAD')
        for ref in ('main', 'dev', f'v{version}^{{}}'):
            self.assertEqual(self.git('rev-parse', ref), head)
        self.assertEqual(self.git('cat-file', '-t', f'v{version}'), 'tag')
        for ref in ('refs/heads/main', 'refs/heads/dev', f'refs/tags/v{version}^{{}}'):
            self.assertEqual(self.git('ls-remote', 'origin', ref).split()[0], head)
        self.assertEqual(self.git('ls-remote', 'origin', 'refs/heads/feat/maint-6.8.2'), '')

    def test_help_uses_r3el_metadata(self):
        result = self.release('--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(VERSION_FILE, result.stdout)
        self.assertIn('Likely next version: 6.8.1', result.stdout)
        self.assert_no_release()

    def test_invalid_versions_are_rejected(self):
        for version in ('v6.8.1', '6.08.1', '6.8.1-01'):
            with self.subTest(version=version):
                result = self.release(version, 'Maintenance')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Use a version', result.stderr)
                self.assert_no_release()

    def test_dirty_checkout_is_rejected(self):
        (self.repository / 'feature.txt').write_text('Uncommitted work\n')
        result = self.release('6.8.1', 'Maintenance')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Commit or stash', result.stderr)
        self.assert_no_release()

    def test_cancellation_leaves_branches_and_files_unchanged(self):
        result = self.release('6.8.1', 'Maintenance', reply='n')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('Release cancelled', result.stdout)
        self.assert_no_release()

    def test_noninteractive_release_is_rejected(self):
        result = self.release('6.8.1', 'Maintenance')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Confirmation requires an interactive terminal', result.stderr)
        self.assert_no_release()
