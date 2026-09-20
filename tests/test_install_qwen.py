"""Exercise installer branches without modifying host services or accounts."""

import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    'install_qwen', Path(__file__).resolve().parents[1] / 'scripts/install-qwen.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class QwenInstallerTests(unittest.TestCase):
    def test_existing_service_is_not_modified_or_started(self):
        with patch.object(installer.subprocess, 'run', return_value=Mock(stdout='loaded\n')) as run:
            installer.install_qwen()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][-1], 'qwen-server.service')

    def test_masked_broken_and_unknown_services_are_not_overwritten(self):
        for state in ('masked', 'error', 'bad-setting', ''):
            with self.subTest(state=state), patch.object(
                installer.subprocess, 'run', return_value=Mock(stdout=state),
            ) as run:
                with self.assertRaises(RuntimeError):
                    installer.install_qwen()
                self.assertEqual(run.call_count, 1)

    def test_systemctl_failure_propagates(self):
        with patch.object(installer.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'systemctl')):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.install_qwen()

    def test_missing_assets_fail_before_account_or_unit_changes(self):
        with patch.object(installer.subprocess, 'run', return_value=Mock(stdout='not-found')) as run:
            with patch.object(Path, 'is_file', return_value=False):
                with self.assertRaisesRegex(RuntimeError, 'llama.cpp'):
                    installer.install_qwen()
            self.assertEqual(run.call_count, 1)

    def test_new_service_matches_ax3l_model_flags_and_is_independent(self):
        commands = []
        artifacts = {}

        def execute(args, **kwargs):
            commands.append(tuple(args))
            if args[0] == 'systemctl' and args[1] == 'show':
                return Mock(stdout='not-found\n')
            if args[0] == 'getent':
                return Mock(returncode=2)
            if args[0] == 'install' and args[1] == '-m':
                artifacts[args[-1]] = Path(args[-2]).read_text()
            return Mock(returncode=0)

        with patch.object(installer.subprocess, 'run', side_effect=execute), \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(installer.os, 'access', return_value=True):
            installer.install_qwen()
        unit = artifacts['/etc/systemd/system/qwen-server.service']
        for value in ('Qwen3.5-4B-Q4_K_M.gguf', '"-c" "12288"', '"--port" "27770"',
                      '"--metrics"', '"--jinja"', 'ProtectSystem=strict', 'User=qwen'):
            self.assertIn(value, unit)
        self.assertNotIn('/opt/prod/r3el', unit)
        self.assertNotIn('/opt/prod/ax3l', unit)
        self.assertEqual(artifacts['/etc/qwen-server/mcp.json'], '{"mcpServers": {}}\n')
        self.assertIn(('groupadd', '--system', 'qwen'), commands)
        self.assertIn(('systemctl', 'daemon-reload'), commands)
        self.assertFalse(any(cmd[0] == 'systemctl' and cmd[1] in ('start', 'stop', 'enable', 'disable')
                             for cmd in commands))

    def test_systemd_argument_escaping(self):
        self.assertEqual(installer.quote('/a b/%x/$x'), '"/a b/%%x/$$x"')

    def test_missing_model_does_not_provision_accounts(self):
        with patch.object(installer.subprocess, 'run', return_value=Mock(stdout='not-found')) as run, \
                patch.object(Path, 'is_file', side_effect=[True, False]), \
                patch.object(installer.os, 'access', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'GGUF'):
                installer.install_qwen()
        self.assertEqual(run.call_count, 1)

    def test_service_account_access_failure_prevents_unit_installation(self):
        commands = []

        def execute(args, **kwargs):
            commands.append(tuple(args))
            if args[0] == 'runuser':
                raise subprocess.CalledProcessError(1, args)
            return Mock(stdout='not-found', returncode=0)

        with patch.object(installer.subprocess, 'run', side_effect=execute), \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(installer.os, 'access', return_value=True):
            with self.assertRaises(subprocess.CalledProcessError):
                installer.install_qwen()
        self.assertFalse(any(cmd[0] in ('install', 'groupadd', 'useradd') for cmd in commands))
