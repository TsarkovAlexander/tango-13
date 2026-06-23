#!/usr/bin/env bash
set -euo pipefail

: "${FIRECRACKER_BIN:?set FIRECRACKER_BIN}"
: "${JAILER_BIN:?set JAILER_BIN}"
: "${KERNEL_IMAGE:?set KERNEL_IMAGE}"
: "${ROOTFS_IMAGE:?set ROOTFS_IMAGE}"

for path in "$FIRECRACKER_BIN" "$JAILER_BIN" "$KERNEL_IMAGE" "$ROOTFS_IMAGE"; do
  test -e "$path" || {
    echo "missing required artifact: $path" >&2
    exit 1
  }
done

test -r /dev/kvm || {
  echo "/dev/kvm is not readable by the current user" >&2
  exit 1
}

command -v timeout >/dev/null || {
  echo "timeout command is required" >&2
  exit 1
}

work_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

cat >"$work_dir/input.json" <<'JSON'
{"sample":"deterministic"}
JSON

cat >"$work_dir/vm-config.json" <<JSON
{
  "boot-source": {
    "kernel_image_path": "$KERNEL_IMAGE",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "path_on_host": "$ROOTFS_IMAGE",
      "is_root_device": true,
      "is_read_only": true
    }
  ],
  "machine-config": {
    "vcpu_count": 1,
    "mem_size_mib": 128
  },
  "network-interfaces": []
}
JSON

echo "host capability checks passed"
echo "next: launch Firecracker with $work_dir/vm-config.json and verify bounded output/cleanup"
timeout 2 "$FIRECRACKER_BIN" --version
