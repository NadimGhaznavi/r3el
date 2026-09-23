#!/usr/bin/env bash
# Update the r3el installation from this checkout.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: sudo scripts/upgrade.sh

Updates the installation at DR3el.BASE_DIR via the r3el install-services.sh
helper, which installs the one-batch server and starts/enables r3el-control.
Reuses or installs the shared Qwen service and defaults R3EL_LLM_URL to it.
Start Qwen and wait for health readiness before starting a batch. Existing database,
database credentials, and accounts are preserved; no MariaDB administrative access is needed.
Refreshes /etc/r3el/tmdb.env from TMDB_TOKEN and TMDB_KEY in /root/.tmdb.

Run install.sh first. This does not pull Git changes.
HELP
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

if [[ $# == 1 && ( $1 == -h || $1 == --help ) ]]; then
    usage
    exit 0
fi
[[ $# == 0 ]] || { usage >&2; exit 2; }
[[ $EUID == 0 ]] || fail "Run upgrade as root."
checkout_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
service_installer="$checkout_dir/scripts/install-services.sh"
[[ -x $service_installer ]] || fail "Missing executable $service_installer; add the r3el service installer first."
install_dir=$(cd -- "$checkout_dir" && python3 -B -c 'from r3el.constants.DR3el import DR3el; print(DR3el.BASE_DIR)')
[[ -d $install_dir && -f /etc/r3el/database.env ]] || fail "Run install.sh first."
grep -Fxq 'DB_NAME=r3el' /etc/r3el/database.env || fail "Credentials do not belong to r3el."
getent passwd r3el >/dev/null || fail "Missing r3el service account; run install.sh first."
"$service_installer"
printf 'Upgraded %s from %s.\n' "$install_dir" "$checkout_dir"
