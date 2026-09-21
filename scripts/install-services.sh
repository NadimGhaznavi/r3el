#!/usr/bin/env bash
# Deploy R3el's batch and control services after account/DB provisioning.
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
# Deploy the modules and presentation assets used by both R3el services.
modules=(
    server/R3elServer.py
    server/ControlServer.py server/EventPages.py
    server/templates/base.html server/templates/styles.html
    server/templates/events.html server/templates/event.html server/templates/error.html
    server/templates/messages/default.html
    server/templates/messages/files_retrieved.html
    server/templates/messages/batch_failed.html
    server/templates/messages/batch_started.html
    server/templates/messages/batch_completed.html
    server/templates/messages/attempt_started.html
    server/templates/messages/reply_received.html
    server/templates/messages/prompt_sent.html
    server/templates/messages/tool_completed.html
    server/templates/messages/submission_accepted.html
    server/templates/messages/tool_received.html
    server/templates/messages/item_started.html
    server/templates/messages/item_completed.html
    server/templates/messages/batch_cancelled.html
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
    activity/WorkspaceSchema.py interface/WorkspaceDb.py
    entity/MediaFile.py entity/MediaFileBatch.py
)
# Stop previous services before replacing their modules. Batches are started manually.
for unit in r3el-server.service r3el-control.service; do
    if [[ -e /etc/systemd/system/$unit || -L /etc/systemd/system/$unit ]]; then
        systemctl stop "$unit"
    fi
done
for module in "${modules[@]}"; do
    install -D -m 644 -- "$checkout_dir/r3el/$module" "$install_dir/r3el/$module"
done
install -m 644 -- "$checkout_dir/requirements.txt" "$install_dir/requirements.txt"
install -D -m 755 -- "$checkout_dir/scripts/services.sh" "$install_dir/scripts/services.sh"

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
subprocess.run([sys.executable, '-B', '-m', 'r3el.activity.WorkspaceSchema'],
               cwd=sys.argv[1], env=environment, check=True)
PYSCHEMA

unit_dir=$(mktemp -d)
trap 'rm -rf -- "$unit_dir"' EXIT
python3 - "$checkout_dir" "$install_dir" "$unit_dir" <<'PY'
from pathlib import Path
import sys

checkout, app, target = sys.argv[1:]
sys.path.insert(0, checkout)
from r3el.constants.DLlama import DLlama
# Escape paths for systemd's quoted values and specifier expansion.
app = app.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
for unit in ('r3el-server.service', 'r3el-control.service'):
    source = Path(checkout) / 'systemd' / unit
    (Path(target) / unit).write_text(source.read_text().replace('@APP@', app).replace('@LLM_PORT@', str(DLlama.PORT)))
PY
systemd-analyze verify "$unit_dir/r3el-server.service" "$unit_dir/r3el-control.service"
for unit in r3el-server.service r3el-control.service; do
    install -m 644 -- "$unit_dir/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl disable r3el-server.service
systemctl enable --now r3el-control.service
control_port=$(cd -- "$checkout_dir" && python3 -B -c 'from r3el.constants.DR3el import DR3el; print(DR3el.PORT)')
printf 'R3el Control started: http://<server>:%s/\n' "$control_port"
printf 'Installed one-batch r3el-server.service at %s.\n' "$install_dir"
printf 'Start qwen-server.service and wait for its /health endpoint to return HTTP 200 before starting r3el-server.service.\n'
printf 'The local Qwen URL is configured by default; /etc/r3el/server.env can override R3EL_LLM_URL.\n'
