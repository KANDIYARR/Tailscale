# Feature mapping

Baseline: hassio-addons/app-tailscale commit
`c89785a15eed005f99415ba7a9d8925bc8703f56`.

This records source-level feature coverage, not completed Home Assistant runtime
qualification. New upstream releases must be reviewed separately.

| Upstream feature | Implementation in Professional |
| --- | --- |
| Browser authentication / native web UI | `web`, nginx root route |
| MagicDNS | `init-magicdns-proxies`, DNS proxies and reconfiguration services |
| Route acceptance / local route protection | `post-tailscaled`, `protect-subnets` |
| Subnet routes / exit nodes / connector / tags | Dedicated schema, `post-tailscaled` |
| Forwarding / MSS / UDP GRO | `forwarding`, `mss-clamping`, `post-tailscaled` |
| Custom control server | `login_server`; explicit signout before switching |
| Serve / Funnel | `share-homeassistant` |
| Named Tailscale Services | `services` |
| Taildrop | `taildrop` |
| Taildrive | `taildrive`; Home Assistant config path adjusted |
| Userspace / DERP / logging preferences | `tailscaled`, stage-two hook |
| Health checks | `healthcheck` |
| AppArmor / S6 dependency management | Included profile and S6 v3 services |

Professional-only additions: dashboard, three-step setup, optional auth-key
entry/clearing, explicit device name, validated extra arguments, stale-edit
protection, credential-free diagnostic summary, and 1.0.0 migration.

Expected differences: DNS acceptance defaults to false; the UI opens the
Professional dashboard first; Home Assistant config is `/homeassistant`; own
state remains `/config/tailscale`; no automatic forced reauthentication when
switching control servers. Broad privileges are now required for feature parity.
