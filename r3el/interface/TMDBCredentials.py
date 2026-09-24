"""Read CLI credentials without executing shell configuration files."""

import os
from pathlib import Path
import shlex

from r3el.interface.TMDB import TMDBError


class TMDBCredentials:
    @staticmethod
    def token() -> str:
        token = os.environ.get('TMDB_TOKEN', '').strip()
        if token:
            if any(character.isspace() for character in token):
                raise TMDBError('TMDB_TOKEN must be a TMDB API Read Access Token without whitespace.')
            return token
        for path in (Path('/etc/r3el/tmdb.env'), Path.home() / '.tmdb'):
            try:
                contents = path.read_text()
            except (FileNotFoundError, PermissionError):
                continue
            except OSError:
                raise TMDBError(f'Unable to read TMDB credentials from {path}.') from None
            try:
                for line in contents.splitlines():
                    fields = shlex.split(line, comments=True)
                    if fields[:1] == ['export']:
                        fields = fields[1:]
                    if len(fields) == 1 and fields[0].startswith('TMDB_TOKEN='):
                        token = fields[0].split('=', 1)[1]
                        if not token or any(character.isspace() for character in token):
                            raise ValueError
                        return token
            except ValueError:
                raise TMDBError(f'Invalid TMDB credentials in {path}.') from None
        raise TMDBError('Set TMDB_TOKEN or configure it in /etc/r3el/tmdb.env or ~/.tmdb.')
