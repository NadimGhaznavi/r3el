#!/usr/bin/env bash
# Deploy the minimal R3el service after install.sh provisions its account/DB.
set -euo pipefail
umask 022

usage() {
    printf 'Usage: sudo scripts/install-services.sh\n'
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
[[ $EUID == 0 ]] || fail "Run service installation as root."
checkout_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
install_dir=$(cd -- "$checkout_dir" && python3 -B - <<'PY'
from pathlib import Path
from r3el.constants.DR3el import DR3el

path = Path(DR3el.BASE_DIR)
checkout = Path.cwd().resolve()
resolved = path.resolve()
if not path.is_absolute() or len(resolved.parts) < 4 or resolved == checkout or resolved in checkout.parents or checkout in resolved.parents:
    raise SystemExit("DR3el.BASE_DIR must be an absolute installation path separate from the checkout, at least three levels deep.")
print(resolved)
PY
)
[[ -d $install_dir && -f /etc/r3el/database.env ]] || fail "Run install.sh first."
getent passwd r3el >/dev/null || fail "Run install.sh first to create the r3el account."
getent group r3el >/dev/null || fail "Missing r3el group; run install.sh first."

if [[ ! -x $install_dir/.venv/bin/python ]]; then
    python3 -m venv "$install_dir/.venv"
fi
"$install_dir/.venv/bin/python" -m pip install -r "$checkout_dir/requirements.txt"
chgrp -R r3el "$install_dir/.venv"
chmod -R g+rX "$install_dir/.venv"
# Deploy only the working R3el modules; the checkout also contains legacy code.
modules=(
    server/R3elServer.py
    constants/DR3el.py constants/DDbMgr.py constants/DEventCategory.py constants/DEventName.py
    entity/EventCategory.py entity/LogEvent.py
    interface/DbMgr.py interface/EventLogDb.py interface/FileMgr.py
    activity/EventSchema.py activity/EventReport.py activity/ServerLifecycle.py
)
for module in "${modules[@]}"; do
    install -D -m 644 -- "$checkout_dir/r3el/$module" "$install_dir/r3el/$module"
done
install -m 644 -- "$checkout_dir/requirements.txt" "$install_dir/requirements.txt"

# Read credentials as data and initialize the schema explicitly before restart.
"$install_dir/.venv/bin/python" - "$install_dir" <<'PYSCHEMA'
import os
from pathlib import Path
import subprocess
import sys

environment = os.environ.copy()
for line in Path('/etc/r3el/database.env').read_text().splitlines():
    key, value = line.split('=', 1)
    environment[key] = value
subprocess.run([sys.executable, '-B', '-m', 'r3el.activity.EventSchema'],
               cwd=sys.argv[1], env=environment, check=True)
PYSCHEMA

unit_dir=$(mktemp -d)
trap 'rm -rf -- "$unit_dir"' EXIT
python3 - "$checkout_dir/systemd/r3el-server.service" "$install_dir" "$unit_dir/r3el-server.service" <<'PY'
from pathlib import Path
import sys

source, app, target = sys.argv[1:]
# Escape paths for systemd's quoted values and specifier expansion.
app = app.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
Path(target).write_text(Path(source).read_text().replace('@APP@', app))
PY
systemd-analyze verify "$unit_dir/r3el-server.service"
install -m 644 -- "$unit_dir/r3el-server.service" /etc/systemd/system/r3el-server.service
systemctl daemon-reload
systemctl enable r3el-server.service
systemctl restart r3el-server.service
systemctl is-active --quiet r3el-server.service
printf 'Installed and started r3el-server.service at %s.\n' "$install_dir"
