#!/usr/bin/env python3
"""Reuse Ax3l's production Qwen service, or provision a shared model service."""

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from r3el.constants.DLlama import DLlama
from r3el.constants.DQwen import DQwen


UNIT = 'qwen-server.service'
CONFIG_DIR = Path('/etc/qwen-server')


def run(*args: str) -> None:
    subprocess.run(args, check=True)


def quote(value: str | Path) -> str:
    """Quote a literal systemd argument, including specifier/dollar escaping."""
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"'


def install_qwen() -> None:
    state = subprocess.run(
        ['systemctl', 'show', '--property=LoadState', '--value', UNIT],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if state == 'loaded':
        print(f'Reusing installed {UNIT}; configuration and running state preserved.')
        return
    if state != 'not-found':
        raise RuntimeError(f'{UNIT} has LoadState={state!r}; repair it before installing.')

    binary = Path(DLlama.BASE_DIR) / DLlama.BIN_DIR / DLlama.SERVER
    model = Path(DLlama.MODEL_DIR) / DQwen.GGUF
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f'Install the llama.cpp executable at {binary} first.')
    if not model.is_file() or not os.access(model, os.R_OK):
        raise RuntimeError(f'Install the Qwen GGUF at {model} first.')

    # This service outlives either application and must not depend on its account.
    for database, command in (
        ('group', ('groupadd', '--system', 'qwen')),
        ('passwd', ('useradd', '--system', '--gid', 'qwen', '--no-create-home',
                    '--home-dir', '/nonexistent', '--shell', '/usr/sbin/nologin', 'qwen')),
    ):
        lookup = subprocess.run(['getent', database, 'qwen'], capture_output=True)
        if lookup.returncode == 2:
            run(*command)
        elif lookup.returncode != 0:
            lookup.check_returncode()
    # Validate the service account's access, not just the installer's root access.
    run('runuser', '-u', 'qwen', '--', 'test', '-x', str(binary))
    run('runuser', '-u', 'qwen', '--', 'test', '-r', str(model))
    command = [str(binary), '--model', str(model), '-c', str(DQwen.CONTEXT_SIZE),
               '--host', DLlama.HOST, '--port', str(DLlama.PORT), '--metrics',
               '--jinja', '--mcp-servers-config', str(CONFIG_DIR / 'mcp.json')]
    template = Path(__file__).resolve().parents[1] / 'systemd' / UNIT
    unit = template.read_text().replace('@WORKING_DIRECTORY@', quote(DLlama.BASE_DIR))
    unit = unit.replace('@QWEN_COMMAND@', ' '.join(quote(arg) for arg in command))
    with TemporaryDirectory() as temporary:
        staging = Path(temporary)
        (staging / UNIT).write_text(unit)
        # R3el owns its MCP conversation; no Ax3l tools are registered here.
        (staging / 'mcp.json').write_text('{"mcpServers": {}}\n')
        run('systemd-analyze', 'verify', str(staging / UNIT))
        run('install', '-d', '-m', '755', str(CONFIG_DIR))
        run('install', '-m', '644', str(staging / 'mcp.json'), str(CONFIG_DIR / 'mcp.json'))
        run('install', '-m', '644', str(staging / UNIT), f'/etc/systemd/system/{UNIT}')
    run('systemctl', 'daemon-reload')
    print(f'Installed shared {UNIT}; left stopped and disabled.')


if __name__ == '__main__':
    if os.geteuid() != 0:
        sys.exit('Run Qwen service installation as root.')
    install_qwen()
