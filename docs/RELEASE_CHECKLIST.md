# Release qualification

Automated gates:

- [ ] Python unit and HTTP integration suite passes.
- [ ] Configuration, feature coverage and S6 dependency checks pass.
- [ ] Native amd64 image builds; Tailscale, Python and nginx smoke checks pass.
- [ ] Native aarch64 image builds; Tailscale, Python and nginx smoke checks pass.
- [ ] Dashboard renders on desktop and mobile; setup steps and error states work.

Actual Home Assistant host checks (not implied by CI):

- [ ] Clean install with browser login and with an auth key.
- [ ] Upgrade from 1.0.0 preserves node identity and old managed arguments.
- [ ] Clear auth key, restart and confirm persistent login.
- [ ] Signout/re-enrollment and custom Headscale server behavior.
- [ ] DNS acceptance, route acceptance, subnet advertising and exit-node modes.
- [ ] Serve, Funnel and named Services with required tailnet permissions.
- [ ] Taildrop and each opt-in Taildrive share.
- [ ] Userspace mode, network interruption, approval and expired-key states.
- [ ] AppArmor enforcement and protected-mode compatibility.
- [ ] Cold backup/restore and clean daemon shutdown.

Enable only the features under test. Perform host networking tests with an
independent way to access the Home Assistant host. Record results per architecture.
