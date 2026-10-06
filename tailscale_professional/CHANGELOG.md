# Changelog

## 2.0.0

- Incorporate the MIT-licensed community Tailscale networking implementation,
  retaining MagicDNS, routes, exit nodes, connector, Serve/Funnel, Services,
  Taildrop, Taildrive, Headscale settings, userspace mode and health checks.
- Add a responsive dashboard with light/dark themes and guided setup.
- Retain auth-key enrollment, add explicit key removal and diagnostic export.
- Persist setup through Supervisor with request protection and stale-edit checks.
- Preserve the 1.0.0 identity path and migrate managed CLI arguments to settings.
- Move process management to S6 Overlay v3's dependency graph.
- Expand privileges/mounts to support the community networking features.
- Drop deprecated armv7; support native amd64/aarch64 builds.
- Add attribution, tests, CI and release verification documentation.

## 1.0.0

- Initial TUN-based Tailscale add-on with persistent identity, optional auth key,
  advanced CLI arguments and S6 supervision.
