"""Copy TMDB credentials as data into the root-owned service configuration."""

import os
from pathlib import Path
import re
import shlex
import tempfile


def install_credentials(source: Path = Path('/root/.tmdb'),
                        destination: Path = Path('/etc/r3el/tmdb.env')) -> None:
    values = {}
    for line in source.read_text().splitlines():
        try:
            fields = shlex.split(line, comments=True)
        except ValueError:
            raise ValueError('Invalid TMDB credentials file syntax.') from None
        if fields[:1] == ['export']:
            fields = fields[1:]
        if not fields:
            continue
        if len(fields) != 1 or '=' not in fields[0]:
            raise ValueError('Expected TMDB_TOKEN and TMDB_KEY assignments.')
        name, value = fields[0].split('=', 1)
        if name not in ('TMDB_TOKEN', 'TMDB_KEY') or name in values:
            raise ValueError('Expected one TMDB_TOKEN and one TMDB_KEY assignment.')
        if not re.fullmatch(r'[A-Za-z0-9._~-]+', value):
            raise ValueError('Invalid TMDB credential value.')
        values[name] = value
    if set(values) != {'TMDB_TOKEN', 'TMDB_KEY'}:
        raise ValueError('TMDB_TOKEN and TMDB_KEY are both required.')
    # mkstemp creates mode 0600; replace atomically without following destination symlinks.
    descriptor, temporary = tempfile.mkstemp(prefix='.tmdb-', dir=destination.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            for name in ('TMDB_TOKEN', 'TMDB_KEY'):
                stream.write(f'{name}={values[name]}\n')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    if os.geteuid() != 0:
        raise SystemExit('Run TMDB credential installation as root.')
    try:
        install_credentials()
    except (OSError, ValueError):
        raise SystemExit('Unable to install TMDB credentials; check /root/.tmdb and /etc/r3el.') from None
