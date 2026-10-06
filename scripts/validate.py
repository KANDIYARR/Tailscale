"""Static release invariants, schema parity and S6 dependency checks."""
import json
from pathlib import Path
import subprocess
import yaml
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'tailscale_professional'
config = yaml.safe_load((APP / 'config.yaml').read_text())
defaults = json.loads((APP / 'defaults.json').read_text())
assert config['options'] == defaults
assert config['name'] == 'Tailscale Professional'
assert config['slug'] == 'tailscale_professional'
assert config['init'] is False
assert config['ingress_entry'] == 'professional/'
assert config['arch'] == ['aarch64', 'amd64']
assert config['schema']['auth_key'] == 'password?'
assert 'SYS_ADMIN' in config['privileged']
features = {'accept_dns', 'accept_routes', 'advertise_connector', 'advertise_exit_node', 'advertise_routes', 'advertise_tags', 'always_use_derp', 'exit_node', 'log_suppression', 'log_upload', 'login_server', 'share_homeassistant', 'share_on_port', 'services', 'snat_subnet_routes', 'stateful_filtering', 'taildrive', 'taildrop', 'userspace_networking'}
assert features <= config['schema'].keys(), 'Upstream feature removed from schema'
for p in APP.rglob('*.yaml'): yaml.safe_load(p.read_text())
rc=APP/'rootfs/etc/s6-overlay/s6-rc.d'
for p in rc.rglob('dependencies.d/*'):
    assert (rc/p.name).exists() or p.name in {'base', 'legacy-services', 'user'}, f'Missing dependency {p}'
for p in (APP/'rootfs').rglob('*'):
    if p.is_file() and p.read_bytes().startswith((b'#!/command/with-contenv bash', b'#!/usr/bin/with-contenv bash', b'#!/bin/bash')):
        subprocess.run(['bash','-O','extglob','-n',str(p)],check=True)
for p in (APP/'rootfs/opt/professional').glob('*.py'): compile(p.read_text(),str(p),'exec')
print('Configuration, feature parity, Python syntax and S6 dependencies: PASS')
