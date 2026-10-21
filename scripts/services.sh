#!/usr/bin/env bash
# Start or stop R3el's services in dependency order.
set -euo pipefail

usage() {
    printf 'Usage: scripts/services.sh start|stop|restart\n'
}

if [[ $# == 1 && ( $1 == -h || $1 == --help ) ]]; then
    usage
    exit 0
fi
[[ $# == 1 && ( $1 == start || $1 == stop || $1 == restart ) ]] || { usage >&2; exit 2; }

system_admin=()
if [[ $EUID != 0 ]]; then
    system_admin=(sudo)
fi

if [[ $1 == start || $1 == restart ]]; then
    install_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
    (cd -- "$install_dir" && "$install_dir/.venv/bin/python" -B -m r3el.interface.Configuration)
    if [[ $1 == restart ]]; then
        "${system_admin[@]}" systemctl stop r3el-server.service r3el-control.service
    fi
    printf 'Starting r3el-control.service.\n'
    "${system_admin[@]}" systemctl start r3el-control.service
    printf 'Starting r3el-server.service.\n'
    "${system_admin[@]}" systemctl start r3el-server.service
else
    for unit in r3el-server.service r3el-control.service; do
        printf 'Stopping %s.\n' "$unit"
        "${system_admin[@]}" systemctl stop "$unit"
    done
fi
