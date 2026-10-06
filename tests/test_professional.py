"""Regression tests for enrollment, migration and the Ingress security boundary."""
import copy
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tailscale_professional/rootfs/opt/professional'))
from options import OptionsError, merge_defaults, migrate_arguments, setup_options, validate
from server import Dashboard, handler_for, public_status, revision
DEFAULTS = json.loads((ROOT / 'tailscale_professional/defaults.json').read_text())

class OptionsTests(unittest.TestCase):
    def test_defaults_validate(self):
        validate(DEFAULTS)

    def test_upgrade_preserves_existing_preferences(self):
        old = {'auth_key': 'secret123', 'extra_args': ['--hostname=kitchen', '--accept-dns=true', '--advertise-routes=192.168.1.0/24', '--ssh']}
        result = merge_defaults(DEFAULTS, migrate_arguments(old))
        self.assertEqual(result['hostname'], 'kitchen')
        self.assertTrue(result['accept_dns'])
        self.assertEqual(result['advertise_routes'], ['192.168.1.0/24'])
        self.assertEqual(result['extra_args'], ['--ssh'])
        self.assertEqual(result['auth_key'], 'secret123')
        validate(result)

    def test_blank_password_preserves_existing_secret(self):
        existing = dict(DEFAULTS, auth_key='!secret tailscale_key')
        self.assertEqual(setup_options(existing, {'auth_key': ''})['auth_key'], existing['auth_key'])
        self.assertNotIn('auth_key', setup_options(existing, {'clear_auth_key': True}))

    def test_setup_preserves_advanced_features(self):
        existing = dict(DEFAULTS, share_homeassistant='serve', taildrop=True, services=[{'name': 'svc:test'}])
        result = setup_options(existing, {'hostname': 'office'})
        self.assertTrue(result['taildrop'])
        self.assertEqual(result['services'], existing['services'])
        self.assertEqual(result['share_homeassistant'], 'serve')

    def test_rejects_route_conflicts_and_invalid_networks(self):
        for values in ({'advertise_exit_node': True, 'exit_node': '100.64.0.1'}, {'advertise_routes': ['192.168.1.5/24']}, {'advertise_routes': ['garbage']}):
            with self.subTest(values=values), self.assertRaises(OptionsError):
                validate(dict(DEFAULTS, **values))

    def test_shell_metacharacters_are_not_evaluated(self):
        # Arguments are data; managed flags and line breaks are denied.
        self.assertEqual(validate(dict(DEFAULTS, extra_args=['--operator=$(id)']))['extra_args'], ['--operator=$(id)'])
        for value in ('--auth-key=tskey-test', '--force-reauth', '--reset', '--accept-dns=true', '--hostname=one\n--ssh', '$(id)', '--help'):
            with self.subTest(value=value), self.assertRaises(OptionsError):
                validate(dict(DEFAULTS, extra_args=[value]))

    def test_control_server_validation(self):
        validate(dict(DEFAULTS, login_server='http://headscale.local:8080'))
        for value in ('javascript:alert(1)', 'https://user:secret@host', 'https://host/?key=secret'):
            with self.subTest(value=value), self.assertRaises(OptionsError):
                validate(dict(DEFAULTS, login_server=value))

    def test_type_and_field_validation(self):
        for patch in ({'taildrive': {'ssl': True}}, {'accept_dns': 'true'}, {'auth_key': 123}, {'hostname': 'a b'}, {'clear_auth_key': 'yes'}):
            with self.subTest(patch=patch), self.assertRaises(OptionsError):
                setup_options(DEFAULTS, patch)

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.stored = dict(copy.deepcopy(DEFAULTS), auth_key='tskey-private-secret')
        self.calls = []
        def supervisor(method, path, data=None):
            self.calls.append((method, path, data))
            if method == 'GET': return {'options': copy.deepcopy(self.stored)}
            if path.endswith('/options'): self.stored = copy.deepcopy(data['options'])
            return {}
        self.runner = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps({'BackendState': 'Running', 'Self': {'Online': True, 'HostName': 'home', 'TailscaleIPs': ['100.64.0.1']}, 'AuthURL': 'https://secret.example/token', 'PrivateNodeKey': 'not-for-ui', 'Health': ['See https://login.example/secret tskey-secret'], 'Peer': {'a': {'Online': True}}}), ''))
        self.app = Dashboard('proxy-secret', api=supervisor, runner=self.runner)

    def test_session_does_not_leak_credentials(self):
        payload = self.app.session()
        text = json.dumps(payload)
        for secret in ('tskey-private', 'https://secret.example', 'PrivateNodeKey', 'tskey-secret', 'login.example'):
            self.assertNotIn(secret, text)
        self.assertTrue(payload['has_auth_key'])
        self.assertEqual(payload['status']['peers_online'], 1)

    def test_status_cache_and_timeout(self):
        self.app.status(); self.app.status()
        self.assertEqual(self.runner.call_count, 1)
        self.assertEqual(self.runner.call_args.kwargs['timeout'], 5)
        self.assertNotIn('shell', self.runner.call_args.kwargs)

    def test_unavailable_daemon_is_visible(self):
        self.runner.side_effect = subprocess.TimeoutExpired('tailscale', 5)
        self.assertEqual(self.app.status()['state'], 'Unavailable')

    def test_save_preserves_key_and_detects_conflict(self):
        old_revision = revision(self.stored)
        self.app.save({'revision': old_revision, 'settings': {'hostname': 'new'}})
        self.assertEqual(self.stored['auth_key'], 'tskey-private-secret')
        with self.assertRaises(OptionsError):
            self.app.save({'revision': old_revision, 'settings': {'hostname': 'old'}})

    def test_control_server_change_requires_signout(self):
        with self.assertRaises(OptionsError):
            self.app.save({'revision': revision(self.stored), 'settings': {'login_server': 'https://headscale.example'}})

    def test_diagnostics_has_no_csrf_or_options(self):
        data = self.app.diagnostics()
        self.assertNotIn('csrf', data)
        self.assertNotIn('settings', data)
        self.assertNotIn('tskey-', json.dumps(data))

    def test_http_auth_csrf_and_safe_assets(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        def request(method, path, body=None, headers=None):
            conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse(); result = (response.status, dict(response.getheaders()), response.read()); conn.close(); return result
        try:
            self.assertEqual(request('GET', '/api/session')[0], 403)
            proxy = {'X-Professional-Token': 'proxy-secret'}
            self.assertEqual(request('GET', '/api/session', headers=proxy)[0], 200)
            self.assertEqual(request('GET', '/../../data/options.json', headers=proxy)[0], 404)
            status, headers, body = request('GET', '/', headers=proxy)
            self.assertEqual(status, 200)
            self.assertIn('Content-Security-Policy', headers)
            self.assertIn(b'GUIDED SETUP', body)
            self.assertEqual(request('POST', '/api/setup', '{}', proxy)[0], 403)
            authenticated = dict(proxy, **{'X-CSRF-Token': self.app.csrf, 'Content-Type': 'text/plain'})
            self.assertEqual(request('POST', '/api/setup', '{}', authenticated)[0], 415)
            authenticated['Content-Type'] = 'application/json'
            payload = json.dumps({'revision': revision(self.stored), 'settings': {'hostname': 'office'}})
            self.assertEqual(request('POST', '/api/setup', payload, authenticated)[0], 200)
            self.assertEqual(self.stored['hostname'], 'office')
            self.assertEqual(request('POST', '/api/setup', '[' + ' ' * 17000 + ']', authenticated)[0], 413)
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
