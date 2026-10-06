# Tailscale Professional

Maintainer: Vinoth Sakthivel · Version: 1.0.0

## Installation

For a local installation, copy the `tailscale_professional` directory into
Home Assistant's `/addons` directory. Refresh the add-on/app store, install
Tailscale Professional, configure it, then start it. Repository installations
use `repository.yaml` at the repository root and the same add-on subdirectory.
Add the real repository URL to `repository.yaml` before publishing it.

Example options:

```yaml
auth_key: "tskey-auth-REPLACE_WITH_YOUR_KEY"
extra_args:
  - "--hostname=home-assistant"
  - "--accept-routes=false"
```

Both options may be omitted. A new installation without a key starts the
daemon and logs instructions to configure a key; it does not join a tailnet.
An existing installation resumes its saved identity without requiring a key.
After successful enrollment, remove `auth_key` from the options. The password
field masks its UI display; it does not encrypt options or backup contents.

## Arguments and authentication

Each `extra_args` item is one literal argument, using `--flag` or
`--flag=value`. Shell expansion is never performed. Authentication, reset,
reauthentication and timeout flags are managed by the service.

The service calls `tailscale up --reset --accept-dns=false`, followed by
your arguments. Thus `extra_args` is the complete desired configuration:
removing an option restores that Tailscale preference's default on restart.
Settings changed manually through the CLI are overwritten on restart.
An explicit `--accept-dns=true` overrides the default if desired.

Keys are supplied through a mode-0600 file under `/run/tailscale`, removed
after successful configuration or shutdown. Existing authenticated nodes
do not reuse the configured key. Configuration failures retry after 60 seconds;
check the options and Tailscale administration console if this persists.
Newly authenticated devices may also require administrator approval.

## Routing

Examples include `--advertise-routes=192.168.1.0/24`,
`--advertise-exit-node`, and `--exit-node=100.64.0.10`.
Advertising routes or an exit node requires appropriate host IP forwarding
and Tailscale administrator approval. This add-on does not automatically
change host forwarding sysctls. Selecting an exit node changes outbound
routing in the shared host network namespace; use
`--exit-node-allow-lan-access=true` when local LAN access is required.

## Persistence and shutdown

Identity, preferences and other daemon state reside in `/config/tailscale`,
inside the mapped add-on configuration directory. Include this add-on and
its configuration in backups. Cold backups stop the service for a consistent
copy, briefly disconnecting Tailscale. Do not operate an original installation
and a restored copy simultaneously with the same Tailscale identity.

S6 supervises the wrapper. Shutdown signals stop the active CLI and daemon;
the daemon gets up to 10 seconds to exit before forced termination. A daemon
exit causes S6 to restart the service. Avoid running another tailscaled
instance in the same host network namespace.

## Compatibility and release validation

The requested `armv7` architecture is retained for legacy installations;
current Home Assistant tooling no longer supports it. Alpine 3.22 base
images provide the corresponding architecture-specific build targets.

The exact requested `devices: ["/dev/net/tun:/dev/net/tun"]` and
`addon_config:rw` syntax is accepted for compatibility but is deprecated by
current Supervisor. For a current-only configuration, use
`devices: ["/dev/net/tun"]` and replace the map entry with
`{type: app_config, read_only: false, path: /config}`.

Before a production release, build and run on each supported target, verify
the host's AppArmor/TUN behavior, first enrollment, key removal, restart,
network recovery, routing if enabled, graceful shutdown and backup restoration.
The source includes no privileged host test results. Maintain security updates
for the Home Assistant base image and Alpine's Tailscale package.
