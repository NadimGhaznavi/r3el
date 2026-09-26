#!/usr/bin/env python3
"""Install or run the Linux desktop handler for R3el's local VLC links."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import unquote, urlsplit


def media_path(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != 'r3el-vlc' or parts.netloc or parts.query or parts.fragment:
        raise ValueError('Expected a local r3el-vlc:///path link.')
    path = unquote(parts.path, errors='strict')
    if not path.startswith('/') or path.startswith('//') or '\0' in path:
        raise ValueError('Expected an absolute local media path.')
    return path


def desktop_argument(value: str) -> str:
    """Quote one Exec argument using desktop entry escaping, without a shell."""
    value = value.replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value.replace('\\', '\\\\') + '"'


def install() -> None:
    for command in ('vlc', 'xdg-mime'):
        if shutil.which(command) is None:
            raise ValueError(f'Install {command} on this desktop first.')
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    handler = data / 'r3el/vlc-link.py'
    handler.parent.mkdir(parents=True, exist_ok=True)
    if Path(__file__).resolve() != handler.resolve():
        shutil.copyfile(__file__, handler)
    applications = data / 'applications'
    applications.mkdir(parents=True, exist_ok=True)
    desktop = applications / 'r3el-vlc.desktop'
    desktop.write_text(
        '[Desktop Entry]\nType=Application\nName=R3el VLC\n'
        f'Exec={desktop_argument(sys.executable)} {desktop_argument(str(handler))} %u\n'
        'Terminal=false\nNoDisplay=true\nMimeType=x-scheme-handler/r3el-vlc;\n',
        encoding='utf-8')
    subprocess.run(['xdg-mime', 'default', desktop.name, 'x-scheme-handler/r3el-vlc'], check=True)
    print('R3el VLC links registered for this desktop user.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='Register links for the current desktop user.')
    parser.add_argument('url', nargs='?')
    args = parser.parse_args()
    try:
        if args.install and args.url is None:
            install()
        elif args.url and not args.install:
            path = media_path(args.url)
            if not Path(path).is_file():
                raise ValueError(f'Media file is not accessible on this desktop: {path}')
            subprocess.run(['vlc', '--', path], check=True)
        else:
            parser.error('Supply --install or one media link.')
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
