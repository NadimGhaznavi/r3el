#!/usr/bin/env bash
# Remove the resources provisioned by install.sh for R3el.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: sudo scripts/uninstall.sh

Deletes DR3el.BASE_DIR, /etc/r3el/database.env, the local MariaDB database
and account r3el, and the Linux service user/group r3el.
All data in that database and installation directory is deleted.
Stops, disables, and removes r3el-server.service before deleting resources.
Run as root with MariaDB administrative socket access.
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
[[ $EUID == 0 ]] || fail "Run uninstallation as root."
checkout_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
install_dir=$(cd -- "$checkout_dir" && python3 -B - <<'PYBASE'
from pathlib import Path
from r3el.constants.DR3el import DR3el

path = Path(DR3el.BASE_DIR)
checkout = Path.cwd().resolve()
resolved = path.resolve()
if not path.is_absolute() or len(resolved.parts) < 4 or resolved == checkout or resolved in checkout.parents or checkout in resolved.parents:
    raise SystemExit("DR3el.BASE_DIR must be an absolute installation path separate from the checkout, at least three levels deep.")
print(resolved)
PYBASE
)
config_dir=/etc/r3el
database=r3el
service_account=r3el
admin=(mariadb --protocol=socket --user=root)
command -v mariadb >/dev/null || fail "Install the MariaDB client first."
"${admin[@]}" --batch --skip-column-names -e 'SELECT 1' >/dev/null ||
    fail "MariaDB administrative access failed; configure root socket access first."

credentials_file="$config_dir/database.env"
# Refuse credentials for a different application.
if [[ -e "$credentials_file" ]]; then
    grep -Fxq "DB_NAME=$database" "$credentials_file" ||
        fail "Credentials do not match the selected environment."
fi

unit=r3el-server.service
if [[ -f /etc/systemd/system/$unit || -L /etc/systemd/system/$unit ]]; then
    systemctl disable --now "$unit"
    rm -- "/etc/systemd/system/$unit"
fi
systemctl daemon-reload

"${admin[@]}" <<SQL
DROP DATABASE IF EXISTS \`$database\`;
DROP USER IF EXISTS '$database'@'localhost';
SQL

rm -rf -- "$install_dir"
rm -f -- "$credentials_file"
if [[ -d "$config_dir" ]]; then
    rmdir --ignore-fail-on-non-empty -- "$config_dir"
fi
if getent passwd "$service_account" >/dev/null; then
    userdel "$service_account"
fi
if getent group "$service_account" >/dev/null; then
    groupdel "$service_account"
fi

printf 'Removed %s installation, credentials, database/account %s, and Linux account/group %s.\n' \
    "$install_dir" "$database" "$service_account"
