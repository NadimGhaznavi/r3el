"""CMDB declarations drive production listeners and local clients."""

import ast
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from r3el.constants.DR3el import DR3el
from r3el.interface.Configuration import Configuration
from r3el.interface.Network import Network
from r3el.server import ControlServer, R3elServer


class NetworkConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'conf' / 'r3el.json'
        self.path_patch = patch.object(Configuration, 'path', return_value=self.path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        Configuration.load.cache_clear()
        self.addCleanup(Configuration.load.cache_clear)

    def write(self, values):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(values))

    def test_discovery_metadata_is_literal(self):
        tree = ast.parse(Path('r3el/constants/DR3el.py').read_text())
        declarations = {node.target.id: ast.literal_eval(node.value)
                        for node in ast.walk(tree) if isinstance(node, ast.AnnAssign)
                        and node.target.id in ('CMDB_DATABASES', 'CMDB_NETWORK')}
        self.assertEqual(declarations['CMDB_DATABASES'], DR3el.CMDB_DATABASES)
        self.assertEqual(declarations['CMDB_NETWORK'], DR3el.CMDB_NETWORK)
        self.assertEqual(Configuration.database('R3el'), 'r3el')

    def test_defaults_and_consumers_follow_declaration_by_use(self):
        with patch.object(DR3el, 'CMDB_NETWORK', (
                ('backend', '0.0.0.0', 19081), ('http', '127.0.0.2', 19080))):
            self.assertEqual(Network.binding('http'), ('127.0.0.2', 19080))
            self.assertEqual(Network.destination('http'), ('127.0.0.2', 19080))
            self.assertEqual(Network.endpoint('backend'), 'tcp://0.0.0.0:19081')
            self.assertEqual(Network.endpoint('backend', destination=True), 'tcp://127.0.0.1:19081')
            with patch.object(ControlServer, 'BatchControl') as client:
                with ControlServer.make_server('127.0.0.1', 0):
                    client.assert_called_once_with('tcp://127.0.0.1:19081')
            self.assert_control_arguments([], ('127.0.0.2', 19080, 'tcp://127.0.0.1:19081'))
            self.assert_batch_endpoint([], 'tcp://0.0.0.0:19081')

    def assert_control_arguments(self, arguments, expected):
        with patch('sys.argv', ['control', *arguments]), patch.object(ControlServer, 'make_server') as server:
            server.return_value.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
            ControlServer.main()
            server.assert_called_once_with(*expected)

    def assert_batch_endpoint(self, arguments, expected):
        with patch('sys.argv', ['batch', *arguments]), patch.object(R3elServer.asyncio, 'run') as run:
            R3elServer.main()
            coroutine = run.call_args.args[0]
            self.assertEqual(coroutine.cr_frame.f_locals['args'].zmq_endpoint, expected)
            coroutine.close()

    def test_partial_overrides_cli_and_process_cache(self):
        self.write({'network': {'http': {'port': 19090}, 'backend': {'interface': '0.0.0.0'}}})
        self.assertEqual(Network.binding('http'), ('0.0.0.0', 19090))
        self.assertEqual(Network.destination('backend'), ('127.0.0.1', 42221))
        self.assert_control_arguments(['--host', '127.0.0.2', '--port', '19100', '--zmq-endpoint', 'tcp://127.0.0.3:19101'],
                                      ('127.0.0.2', 19100, 'tcp://127.0.0.3:19101'))
        self.assert_batch_endpoint(['--zmq-endpoint', 'tcp://127.0.0.3:19101'], 'tcp://127.0.0.3:19101')
        self.write({'network': {'http': {'port': 19110}}})
        self.assertEqual(Network.binding('http')[1], 19090)
        Configuration.load.cache_clear()
        self.assertEqual(Network.binding('http')[1], 19110)

    def test_invalid_external_configuration_identifies_setting(self):
        cases = [([], 'object'), ({'extra': {}}, 'network'), ({'network': []}, 'network'),
                 ({'network': {'unknown': {}}}, 'network.unknown'),
                 ({'network': {'http': {'host': 'localhost'}}}, 'network.http'),
                 ({'network': {'http': []}}, 'network.http')]
        for value in ('localhost', '::1', '999.1.1.1', 123, None):
            cases.append(({'network': {'http': {'interface': value}}}, 'network.http.interface'))
        for value in (True, '80', 0, 65536, 80.0, None):
            cases.append(({'network': {'http': {'port': value}}}, 'network.http.port'))
        for value, field in cases:
            with self.subTest(value=value):
                self.write(value)
                with self.assertRaisesRegex(ValueError, field) as error:
                    Configuration.resolve(self.path)
                self.assertIn(str(self.path), str(error.exception))
        self.path.write_text('{')
        with self.assertRaisesRegex(ValueError, 'r3el.json'):
            Configuration.prepare()
        self.assertEqual(self.path.read_text(), '{')

    def test_prepare_creates_defaults_and_preserves_existing_file(self):
        Configuration.prepare()
        self.assertEqual(json.loads(self.path.read_text()), Configuration.defaults())
        original = '{ "network": {"http": {"port": 19090}} }\n'
        self.path.write_text(original)
        Configuration.prepare()
        self.assertEqual(self.path.read_text(), original)

    def test_invalid_restart_configuration_prevents_service_actions(self):
        root = Path(self.temporary.name)
        scripts = root / 'scripts'
        scripts.mkdir()
        script = scripts / 'services.sh'
        script.write_text(Path('scripts/services.sh').read_text())
        python = root / '.venv' / 'bin' / 'python'
        python.parent.mkdir(parents=True)
        python.write_text('#!/bin/sh\nprintf "configuration invalid\\n" >&2\nexit 1\n')
        python.chmod(0o755)
        result = subprocess.run(['bash', str(script), 'restart'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, 'configuration invalid\n')
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
