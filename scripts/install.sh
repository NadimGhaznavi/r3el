#!/usr/bin/env bash
# Prepare local MariaDB storage and credentials for an R3el installation.
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: sudo scripts/install.sh

Provisions r3el at DR3el.BASE_DIR, with credentials in /etc/r3el/database.env.
Creates the local MariaDB database/account r3el and Linux service user/group
r3el, without an interactive login or home directory. Existing credentials
are reused; existing account passwords are not reset.

MariaDB must already be running and root must have administrative socket
access. The r3el install-services.sh helper must be present to install and
start the minimal r3el-server service. No release is published.
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
[[ $EUID == 0 ]] || fail "Run installation as root."
checkout_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
service_installer="$checkout_dir/scripts/install-services.sh"
[[ -x $service_installer ]] || fail "Missing executable $service_installer; add the r3el service installer first."
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

command -v mariadb >/dev/null || fail "Install the MariaDB client first."
command -v openssl >/dev/null || fail "Install openssl first."
admin=(mariadb --protocol=socket --user=root)

DB_HOST=localhost
DB_PORT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &&
    python3 -B -c 'from r3el.constants.DDbMgr import DDbMgr; print(DDbMgr.PORT)')
DB_NAME=r3el
DB_USER=$DB_NAME
# Underscores are wildcards in MariaDB database-level grants.
grant_database=${DB_NAME//_/\\_}
credentials_file="$config_dir/database.env"
[[ ! -L "$credentials_file" ]] || fail "Credentials path must not be a symlink."
if [[ -e "$credentials_file" ]]; then
    [[ -f "$credentials_file" && -O "$credentials_file" ]] ||
        fail "Existing credentials must be a regular file owned by the current user."
    [[ $(stat -c '%a' "$credentials_file") == 600 ]] ||
        fail "Existing credentials must have mode 600."
    # Accept only the exact generated contract; never execute a credentials file.
    mapfile -t config_lines < "$credentials_file"
    [[ ${#config_lines[@]} == 5 ]] || fail "Invalid credentials file format."
    [[ ${config_lines[0]} == "DB_HOST=$DB_HOST" &&
       ${config_lines[1]} == "DB_PORT=$DB_PORT" &&
       ${config_lines[2]} == "DB_NAME=$DB_NAME" &&
       ${config_lines[3]} == "DB_USER=$DB_USER" &&
       ${config_lines[4]} =~ ^DB_PASSWORD=([a-f0-9]{64})$ ]] ||
        fail "Existing credentials do not match the r3el installation contract."
    DB_PASSWORD=${BASH_REMATCH[1]}
else
    DB_PASSWORD=$(openssl rand -hex 32)
fi

# All SQL identifiers are fixed by the validated environment; the password is hex.
# Check administrative access before creating files or directories.
"${admin[@]}" --batch --skip-column-names -e 'SELECT 1' >/dev/null ||
    fail "MariaDB administrative access failed; configure root socket access first."

umask 077
mkdir -p -- "$config_dir"
service_account=r3el
if ! getent group "$service_account" >/dev/null; then
    groupadd --system "$service_account"
fi
if ! getent passwd "$service_account" >/dev/null; then
    useradd --system --gid "$service_account" --no-create-home \
        --home-dir /nonexistent --shell /usr/sbin/nologin "$service_account"
fi
install -d -m 755 -o "$service_account" -g "$service_account" -- "$install_dir"
if [[ ! -e "$credentials_file" ]]; then
    # Keep the generated password if provisioning fails, so a rerun can recover.
    (
        set -o noclobber
        printf 'DB_HOST=%s\nDB_PORT=%s\nDB_NAME=%s\nDB_USER=%s\nDB_PASSWORD=%s\n' \
            "$DB_HOST" "$DB_PORT" "$DB_NAME" "$DB_USER" "$DB_PASSWORD" > "$credentials_file"
    )
fi

"${admin[@]}" <<SQL
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';
GRANT ALL PRIVILEGES ON \`$grant_database\`.* TO '$DB_USER'@'localhost';
SQL

MYSQL_PWD="$DB_PASSWORD" mariadb --no-defaults --protocol=socket \
    --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" --database="$DB_NAME" \
    --batch --skip-column-names -e 'SELECT 1' >/dev/null ||
    fail "Database login failed. An existing account may have a different password; it was not reset."

printf 'Installation directory ready: %s\n' "$install_dir"
printf 'Credentials ready: %s\n' "$credentials_file"
printf 'Verified local MariaDB account %s on database %s.\n' "$DB_USER" "$DB_NAME"

"$service_installer"
