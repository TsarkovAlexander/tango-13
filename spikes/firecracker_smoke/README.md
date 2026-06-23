# Firecracker Smoke Spike

This spike is the first implementation gate for the direct Firecracker path. Run it on the target EC2 instance family before building production capacity around sandbox hosts.

## Success Criteria

- `/dev/kvm` is present and accessible by the sandbox executor user.
- `firecracker` and `jailer` binaries are installed and pinned.
- A minimal kernel and rootfs boot successfully.
- Input is passed through a read-only file or vsock channel.
- Output is written to a bounded result file.
- CPU, memory, disk, and wall-clock limits are enforced by the host.
- Guest networking is absent by default.
- Temporary state is removed after the VM exits.

## Manual Inputs

Set these environment variables before running `run.sh`:

- `FIRECRACKER_BIN`: path to the Firecracker binary.
- `JAILER_BIN`: path to the jailer binary.
- `KERNEL_IMAGE`: path to the pinned kernel image.
- `ROOTFS_IMAGE`: path to the pinned read-only rootfs image.

The script intentionally fails fast if any required host capability or artifact is missing.
