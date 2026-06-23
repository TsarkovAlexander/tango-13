#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="/var/log/tango-sandbox-bootstrap.log"
FIRECRACKER_BIN="${FIRECRACKER_BIN:-/usr/local/bin/firecracker}"
JAILER_BIN="${JAILER_BIN:-/usr/local/bin/jailer}"
KERNEL_IMAGE="${KERNEL_IMAGE:-/opt/tango/images/vmlinux}"
ROOTFS_IMAGE="${ROOTFS_IMAGE:-/opt/tango/images/rootfs.ext4}"
EXECUTOR_SERVICE="${EXECUTOR_SERVICE:-tango-sandbox-executor.service}"

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"
chmod 0640 "$LOG_FILE"
exec >>"$LOG_FILE" 2>&1

log() {
  printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

require_executable() {
  local path="$1"
  [ -x "$path" ] || fail "$path must exist and be executable"
}

require_file() {
  local path="$1"
  [ -f "$path" ] || fail "$path must exist"
}

extract_version() {
  "$1" --version 2>/dev/null | awk '{print $2}' | sed 's/^v//'
}

log "Starting Tango sandbox host bootstrap"

require_executable "$FIRECRACKER_BIN"
require_executable "$JAILER_BIN"
require_file "$KERNEL_IMAGE"
require_file "$ROOTFS_IMAGE"

[ -c /dev/kvm ] || fail "/dev/kvm character device is missing"
[ -r /dev/kvm ] && [ -w /dev/kvm ] || fail "/dev/kvm must be readable and writable by bootstrap executor"
[ -d /sys/fs/cgroup ] || fail "cgroup filesystem is not mounted"

firecracker_version="$(extract_version "$FIRECRACKER_BIN")"
jailer_version="$(extract_version "$JAILER_BIN")"
[ -n "$firecracker_version" ] || fail "unable to determine Firecracker version"
[ -n "$jailer_version" ] || fail "unable to determine jailer version"
[ "$firecracker_version" = "$jailer_version" ] || fail "Firecracker ($firecracker_version) and jailer ($jailer_version) versions differ"

if [ "${ALLOW_SANDBOX_SWAP:-false}" != "true" ] && awk 'NR > 1 { found = 1 } END { exit found ? 0 : 1 }' /proc/swaps; then
  fail "swap is enabled; disable swap or set ALLOW_SANDBOX_SWAP=true explicitly"
fi

install -d -m 0750 -o root -g root /srv/jailer
install -d -m 0750 -o root -g root /var/lib/tango/sandbox
install -d -m 0750 -o root -g root /var/lib/tango/sandbox/artifacts
install -d -m 0750 -o root -g root /var/lib/tango/sandbox/runs
install -d -m 0750 -o root -g root /var/lib/tango/sandbox/tmp
install -d -m 0750 -o root -g root /var/log/tango

systemctl daemon-reload
systemctl enable --now "$EXECUTOR_SERVICE"

log "Tango sandbox host bootstrap completed"
