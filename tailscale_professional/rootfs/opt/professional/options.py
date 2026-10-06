"""Validated Professional options and Supervisor persistence (MIT, Vinoth Sakthivel)."""
import copy
import ipaddress
import json
import os
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit

OPTIONS_PATH = Path('/data/options.json')
DEFAULTS_PATH = Path('/opt/professional/defaults.json')
MANAGED = {
    'hostname': 'hostname', 'accept-dns': 'accept_dns', 'accept-routes': 'accept_routes',
    'advertise-exit-node': 'advertise_exit_node', 'exit-node': 'exit_node',
    'advertise-connector': 'advertise_connector', 'login-server': 'login_server',
    'stateful-filtering': 'stateful_filtering', 'snat-subnet-routes': 'snat_subnet_routes',
    'advertise-tags': 'advertise_tags', 'advertise-routes': 'advertise_routes',
}
RESERVED = {'auth-key', 'authkey', 'force-reauth', 'reset', 'timeout', 'help', 'qr',
            'json', 'exit-node-allow-lan-access', 'socket'}
BOOLEAN_OPTIONS = {'accept_dns','accept_routes','advertise_exit_node','advertise_connector',
                   'stateful_filtering','snat_subnet_routes','userspace_networking',
                   'always_use_derp','log_suppression','log_upload','taildrop'}
SETUP_FIELDS = {'hostname','auth_key','clear_auth_key','login_server','accept_dns',
                'accept_routes','advertise_exit_node','advertise_routes','userspace_networking'}

class OptionsError(ValueError):
    """Safe, user-facing configuration error; never include an option value."""


def supervisor(method, path, data=None):
    token = os.environ.get('SUPERVISOR_TOKEN')
    if not token:
        raise OptionsError('The Home Assistant Supervisor connection is unavailable.')
    request = urllib.request.Request('http://supervisor' + path, method=method,
        headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
        data=None if data is None else json.dumps(data).encode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result = json.load(response)
        if result.get('result') != 'ok':
            raise OptionsError('Supervisor could not complete the request. Check the add-on logs.')
        return result.get('data', {})
    except (OSError, ValueError) as exc:
        # HTTP errors may echo submitted keys. Never forward their response bodies.
        raise OptionsError('Supervisor could not complete the request. Check the add-on logs.') from None


def merge_defaults(defaults, values):
    result = copy.deepcopy(defaults)
    for key, value in values.items():
        result[key] = merge_defaults(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


def migrate_arguments(values):
    """Move 1.0.0 flags into the new dedicated settings, without losing preferences."""
    result = copy.deepcopy(values)
    remaining = []
    for arg in result.get('extra_args', []):
        if not isinstance(arg, str):
            raise OptionsError('Advanced arguments must be strings.')
        name, sep, value = arg.removeprefix('--').partition('=')
        target = MANAGED.get(name)
        if not arg.startswith('--') or not target:
            remaining.append(arg)
        elif target in BOOLEAN_OPTIONS:
            if sep and value not in ('true', 'false'):
                raise OptionsError('A legacy boolean argument is invalid.')
            result[target] = value != 'false'
        elif target in ('advertise_routes', 'advertise_tags'):
            result[target] = value.split(',') if value else []
        elif sep:
            result[target] = value
        else:
            raise OptionsError('A legacy argument requires --flag=value syntax.')
    result['extra_args'] = remaining
    return result


def validate(values, allow_secret_references=False):
    for key in BOOLEAN_OPTIONS:
        if key in values and type(values[key]) is not bool:
            raise OptionsError('Networking switches must be true or false.')
    hostname = values.get('hostname', '')
    if hostname and (not isinstance(hostname, str) or not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', hostname)):
        raise OptionsError('Device name must be 1–63 letters, numbers or hyphens, with no leading or trailing hyphen.')
    key = values.get('auth_key', '')
    if not isinstance(key, str) or len(key) > 2048 or any(ord(c) < 32 for c in key):
        raise OptionsError('Authentication key is invalid.')
    # Headscale keys need not use Tailscale's tskey- prefix.
    if key and any(c.isspace() for c in key) and not (allow_secret_references and key.startswith('!secret ')):
        raise OptionsError('Authentication keys must not contain whitespace.')
    try:
        server = urlsplit(values.get('login_server', 'https://controlplane.tailscale.com'))
        valid = server.scheme in ('https', 'http') and server.hostname and not server.username and not server.password and not server.query and not server.fragment
        _ = server.port
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise OptionsError('Control server must be an HTTP or HTTPS URL without embedded credentials, query or fragment.')
    if values.get('advertise_exit_node') and values.get('exit_node'):
        raise OptionsError('This device cannot provide an exit node while using another exit node.')
    routes = values.get('advertise_routes', [])
    if not isinstance(routes, list) or len(routes) > 128:
        raise OptionsError('Subnet routes must be a list with at most 128 entries.')
    for route in routes:
        if route == 'local_subnets':
            continue
        try:
            if not isinstance(route, str) or '/' not in route:
                raise ValueError()
            ipaddress.ip_network(route, strict=True)
        except ValueError:
            raise OptionsError('Use a valid subnet such as 192.168.1.0/24, with no host bits set.') from None
    arguments = values.get('extra_args', [])
    if not isinstance(arguments, list) or len(arguments) > 64:
        raise OptionsError('Advanced arguments must be a list with at most 64 entries.')
    for arg in arguments:
        if not isinstance(arg, str) or len(arg) > 2048 or any(ord(c) < 32 for c in arg) or not re.fullmatch(r'--[a-z][a-z0-9-]*(?:=.*)?', arg):
            raise OptionsError('Use one --flag or --flag=value per advanced argument.')
        if arg[2:].split('=', 1)[0] in RESERVED | MANAGED.keys():
            raise OptionsError('An advanced argument duplicates a managed option. Use the dedicated setting instead.')
    return values


def setup_options(existing, patch):
    if not isinstance(patch, dict) or set(patch) - SETUP_FIELDS:
        raise OptionsError('The setup request contains unsupported fields.')
    result = copy.deepcopy(existing)
    for key, value in patch.items():
        if key in ('clear_auth_key', 'auth_key'):
            continue
        if key == 'hostname' and value == '':
            result.pop(key, None)
        else:
            result[key] = value
    if 'clear_auth_key' in patch and type(patch['clear_auth_key']) is not bool:
        raise OptionsError('Clear authentication key must be true or false.')
    if patch.get('clear_auth_key'):
        result.pop('auth_key', None)
    # Blank password means preserve existing key; explicit clear is separate.
    if patch.get('auth_key'):
        result['auth_key'] = patch['auth_key']
    return validate(result, allow_secret_references=True)


def migrate():
    local = json.loads(OPTIONS_PATH.read_text())
    stored = supervisor('GET', '/addons/self/info')['options']
    defaults = json.loads(DEFAULTS_PATH.read_text())
    merged = merge_defaults(defaults, migrate_arguments(stored))
    validate(merged, allow_secret_references=True)
    if merged != stored:
        supervisor('POST', '/addons/self/options', {'options': merged})
    # Keep the current run's snapshot resolved, while Supervisor retains !secret references.
    resolved = merge_defaults(defaults, migrate_arguments(local))
    validate(resolved)
    temporary = OPTIONS_PATH.with_suffix('.professional.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(resolved, handle)
    os.replace(temporary, OPTIONS_PATH)
