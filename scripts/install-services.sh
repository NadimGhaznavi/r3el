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

python3 -B "$checkout_dir/scripts/install-qwen.py"

if [[ ! -x $install_dir/.venv/bin/python ]]; then
    python3 -m venv "$install_dir/.venv"
fi
"$install_dir/.venv/bin/python" -m pip install -r "$checkout_dir/requirements.txt"
chgrp -R r3el "$install_dir/.venv"
chmod -R g+rX "$install_dir/.venv"
# Deploy only the working R3el modules; the checkout also contains legacy code.
modules=(
    server/R3elServer.py
    app/Prompt.py
    app/BatchIdentification.py app/ToolConversation.py
    app/SubmissionHandler.py app/ValidateIdentification.py
    app/prompts/FileContext.py app/prompts/SubmitIdentificationPrompt.py
    app/prompts/InvalidIdentification.py
    app/tools/__main__.py app/tools/server.py
    app/tools/SubmitIdentification.py
    interface/LLM.py interface/IdentificationTools.py
    entity/Identification.py activity/EventWriter.py constants/DZMQ.py
    zmq/ZMQClient.py zmq/ZMQServer.py zmq/ZMQMsg.py
    constants/DR3el.py constants/DDbMgr.py constants/DEventCategory.py constants/DEventName.py
    entity/EventCategory.py entity/LogEvent.py
    interface/DbMgr.py interface/EventLogDb.py interface/FileMgr.py
    activity/EventSchema.py activity/EventReport.py activity/ServerLifecycle.py
)
# Stop the previous service before replacing its modules. Batches are started manually.
if [[ -e /etc/systemd/system/r3el-server.service || -L /etc/systemd/system/r3el-server.service ]]; then
    systemctl stop r3el-server.service
fi
for module in "${modules[@]}"; do
    install -D -m 644 -- "$checkout_dir/r3el/$module" "$install_dir/r3el/$module"
done
install -m 644 -- "$checkout_dir/requirements.txt" "$install_dir/requirements.txt"

# Read credentials as data and initialize the schema explicitly before any batch is started.
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
python3 - "$checkout_dir/systemd/r3el-server.service" "$install_dir" "$unit_dir/r3el-server.service" "$checkout_dir" <<'PY'
from pathlib import Path
import sys

source, app, target, checkout = sys.argv[1:]
sys.path.insert(0, checkout)
from r3el.constants.DLlama import DLlama
# Escape paths for systemd's quoted values and specifier expansion.
app = app.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
Path(target).write_text(Path(source).read_text().replace('@APP@', app).replace('@LLM_PORT@', str(DLlama.PORT)))
PY
systemd-analyze verify "$unit_dir/r3el-server.service"
install -m 644 -- "$unit_dir/r3el-server.service" /etc/systemd/system/r3el-server.service
systemctl daemon-reload
systemctl disable r3el-server.service
printf 'Installed one-batch r3el-server.service at %s.\n' "$install_dir"
printf 'Start qwen-server.service and wait for its /health endpoint to return HTTP 200 before starting r3el-server.service.\n'
printf 'The local Qwen URL is configured by default; /etc/r3el/server.env can override R3EL_LLM_URL.\n'
