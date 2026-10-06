# Tailscale Professional

Maintained by Vinoth Sakthivel. Version 2.0.0.

## Dashboard and setup

Open the Web UI from Home Assistant. The dashboard shows connection state,
device addresses, visible peers, key expiry and Tailscale health messages.

1. Select **Set up connection**. Choose a device name and optionally supply an
   authentication key. Leaving the key empty preserves an existing saved key.
   Use **Remove the saved key** to explicitly clear it after enrollment.
2. Choose DNS, accepted routes, userspace networking and advertised routes.
3. Review the settings, then select **Save and restart**. This persists options
   through Supervisor and restarts only this add-on. A remote Tailscale session
   may disconnect briefly.

If no key is supplied and the device is not enrolled, open **Tailscale controls**
for browser sign-in. Device or route approval may still be required in your
Tailscale administration console. Enrollment keys are used only when login is
required. They are never returned to the dashboard or included in the process
argument list. Password fields mask display; stored options and backups still
contain secrets, so protect your backups.

## Configuration

All community-app configuration options are retained:

- `accept_dns`, `accept_routes`: DNS and advertised route acceptance. DNS defaults
  to false in Professional, preserving the 1.0.0 behavior.
- `advertise_routes`, `advertise_exit_node`, `exit_node`: subnet and exit routing.
  Providing and consuming an exit node simultaneously is rejected. LAN access is
  preserved when an exit node is selected.
- `advertise_connector`, `advertise_tags`: connector and tag preferences.
- `login_server`: Tailscale or a compatible Headscale control server. Sign out
  using Tailscale controls before changing servers; Professional does not force
  reauthentication silently.
- `snat_subnet_routes`, `stateful_filtering`: advanced routing behavior.
- `always_use_derp`: use relay traffic when direct UDP connectivity is problematic.
- `log_upload`, `log_suppression`: Tailscale logging preferences.
- `share_homeassistant`, `share_on_port`: disabled, Serve or Funnel sharing.
- `services`: named Tailscale Services with name, target, protocol, port and path.
- `taildrop`: receive files in `/share/taildrop`.
- `taildrive`: selectively share `local_apps`, `app_configs`, `backup`, `config`,
  `media`, `share` and `ssl`. All are disabled by default.
- `userspace_networking`: userspace mode instead of the host TUN interface.

Professional additionally provides:

- `auth_key`: optional authentication key, including compatible Headscale keys.
- `hostname`: optional device name, up to 63 letters, numbers or hyphens.
- `extra_args`: optional array of literal `--flag` or `--flag=value` arguments.
  Use dedicated options for managed settings. Authentication, timeout, reset and
  reauthentication flags cannot be overridden here. Invalid Tailscale flags can
  prevent connection; the dashboard remains available to help with setup.

The complete settings are applied at startup using `tailscale up --reset`.
Manual CLI preference changes are overwritten on restart. For detailed
networking prerequisites and configuration examples, see the attributed
[upstream reference](UPSTREAM_DOCS.md). Use Professional's own installation URL,
state paths and defaults when that reference differs.

## Networking prerequisites

Subnet routing and exit nodes require host IP forwarding and administrative
approval. Serve/Funnel require appropriate tailnet permissions and HTTPS
capabilities; Home Assistant must permit the local reverse proxy. The add-on
checks the Home Assistant proxy configuration before serving it. Funnel makes
Home Assistant reachable from the public internet when explicitly enabled.

Userspace mode limits host-initiated connections to other tailnet devices.
MagicDNS includes the upstream DNS proxy and route-protection services; follow
the upstream DNS instructions rather than setting 100.100.100.100 directly as a
host network DNS server. Do not run another Tailscale daemon on the same host
network namespace at the same time.

## Persistence, permissions and backups

Professional owns `/config`, mapped from its app configuration directory.
Identity stays in `/config/tailscale`; upgrading from 1.0.0 retains that path.
Home Assistant's configuration is mounted at `/homeassistant` and is exported
as the `config` share only if explicitly enabled in Taildrive. Other directory
mounts follow the community app layout.

`NET_ADMIN` supports TUN and routing, `NET_RAW` supports network operations,
and `SYS_ADMIN` permits the isolated resolver mount used by the DNS integration.
Host D-Bus and Supervisor access support network configuration and integration.
The included AppArmor profile remains enabled. Taildrive's broad directory
mounts include sensitive data: enable individual shares deliberately.

Cold backups stop the add-on to capture consistent state. Include the add-on
configuration in backups, and never run restored and original copies with the
same identity simultaneously.

## Diagnostics and troubleshooting

**Connection report** downloads an allowlisted status summary without keys,
authentication links, full preferences, account profiles or logs. It still
contains device names and network addresses; review it before sharing.

- **Sign-in needed:** open Tailscale controls or supply a valid key.
- **Approval needed:** approve the device in your tailnet administration console.
- **Setup changed elsewhere:** refresh before saving; another editor changed options.
- **Restart did not reconnect:** reopen the dashboard or restart from Home Assistant.
- **Configuration error:** inspect Home Assistant's add-on logs and advanced options.

The dashboard binds only to loopback, uses a private nginx-to-dashboard token,
and rejects setup changes without a per-session request token. Nginx restricts
Ingress traffic to the Home Assistant Supervisor gateway. No dashboard port is
published publicly.

This release supports amd64 and aarch64. Runtime qualification on a real Home
Assistant host is tracked separately from automated unit and container checks.
