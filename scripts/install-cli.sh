#!/usr/bin/env bash
# Install only the standalone TMDB CLI and its Python dependencies.
set -euo pipefail
umask 022

if [[ $# == 1 && ( $1 == -h || $1 == --help ) ]]; then
    printf 'Usage: sudo scripts/install-cli.sh\nInstalls bin/query-tmdb and .venv under /opt/prod/r3el.\n'
    exit 0
fi
if [[ $# != 0 ]]; then
    printf 'Usage: sudo scripts/install-cli.sh\n' >&2
    exit 2
fi
checkout_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
install_dir=/opt/prod/r3el

install -d -m 755 -- "$install_dir" "$install_dir/bin"
if [[ ! -x $install_dir/.venv/bin/python ]]; then
    python3 -m venv "$install_dir/.venv"
fi
"$install_dir/.venv/bin/python" -m pip install -r "$checkout_dir/requirements-cli.txt"

for module in interface/TMDB.py entity/TMDBReference.py; do
    install -D -m 644 -- "$checkout_dir/r3el/$module" "$install_dir/r3el/$module"
done
install -D -m 644 -- "$checkout_dir/scripts/query-tmdb.py" "$install_dir/scripts/query-tmdb.py"
install -m 644 -- "$checkout_dir/requirements-cli.txt" "$install_dir/requirements-cli.txt"
install -m 755 -- "$checkout_dir/scripts/query-tmdb" "$install_dir/bin/query-tmdb"

"$install_dir/bin/query-tmdb" --help
printf '\nInstalled CLI: %s/bin/query-tmdb\nExport TMDB_TOKEN before searching.\n' "$install_dir"
