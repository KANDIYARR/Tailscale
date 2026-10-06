"""Ingress-only dashboard and guided setup. MIT, Vinoth Sakthivel."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import threading
import time
from urllib.parse import urlsplit
from options import OPTIONS_PATH, OptionsError, setup_options, supervisor

STATIC = Path(__file__).parent / 'static'
RUNTIME = Path('/run/tailscale-professional')
VERSION = '2.0.0'
PUBLIC_OPTIONS = ('hostname', 'login_server', 'accept_dns', 'accept_routes',
                  'advertise_exit_node', 'advertise_routes', 'userspace_networking',
                  'share_homeassistant', 'taildrop', 'taildrive', 'exit_node')


def revision(options):
    return hashlib.sha256(json.dumps(options, sort_keys=True).encode()).hexdigest()


def redact(message):
    text = str(message)
    text = re.sub(r'tskey-[A-Za-z0-9_-]+', '[redacted]', text)
    text = re.sub(r'https?://\S+', '[link omitted]', text)
    return text[:500]


def public_status(raw):
    """Allowlist only; never return AuthURL, node keys, user profiles or full prefs."""
    self_node = raw.get('Self') or {}
    peers = list((raw.get('Peer') or {}).values())
    return {
        'state': raw.get('BackendState', 'Unavailable'),
        'online': bool(self_node.get('Online', False)),
        'hostname': self_node.get('HostName', ''),
        'dns_name': self_node.get('DNSName', '').rstrip('.'),
        'addresses': self_node.get('TailscaleIPs') or raw.get('TailscaleIPs') or [],
        'key_expiry': self_node.get('KeyExpiry'),
        'peers_online': sum(bool(peer.get('Online')) for peer in peers),
        'peers_total': len(peers),
        'health': [redact(item) for item in (raw.get('Health') or [])][:20],
        'tailscale_version': raw.get('Version', ''),
    }


class Dashboard:
    def __init__(self, proxy_token, api=supervisor, runner=subprocess.run):
        self.proxy_token = proxy_token
        self.csrf = secrets.token_urlsafe(32)
        self.api = api
        self.runner = runner
        self.status_lock = threading.Lock()
        self.mutation_lock = threading.Lock()
        self.cached_status = None
        self.cached_at = 0

    def status(self):
        with self.status_lock:
            if self.cached_status is not None and time.monotonic() - self.cached_at < 5:
                return self.cached_status
            try:
                output = self.runner(['/opt/tailscale', 'status', '--json'],
                    capture_output=True, text=True, timeout=5, check=False)
                raw = json.loads(output.stdout)
                status = public_status(raw)
            except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
                status = public_status({})
                status['health'] = ['The Tailscale service is starting or unavailable.']
            self.cached_status = status
            self.cached_at = time.monotonic()
            return status

    def session(self):
        info = self.api('GET', '/addons/self/info')
        values = info.get('options', {})
        return {'version': VERSION, 'csrf': self.csrf, 'revision': revision(values),
            'settings': {key: values[key] for key in PUBLIC_OPTIONS if key in values},
            'has_auth_key': bool(values.get('auth_key')), 'status': self.status()}

    def diagnostics(self):
        # Read-only summary, deliberately excludes options, auth URL, tokens and logs.
        return {'version': VERSION, 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'status': self.status(), 'note': 'Contains device names and network addresses; review before sharing.'}

    def save(self, body):
        if not isinstance(body, dict) or set(body) != {'revision', 'settings'}:
            raise OptionsError('Invalid setup request.')
        with self.mutation_lock:
            current = self.api('GET', '/addons/self/info').get('options', {})
            if body['revision'] != revision(current):
                raise OptionsError('Settings changed elsewhere. Refresh this page before saving.')
            updated = setup_options(current, body['settings'])
            if updated.get('login_server') != current.get('login_server') and self.status()['state'] == 'Running':
                raise OptionsError('Sign out through Tailscale controls before changing control servers.')
            self.api('POST', '/addons/self/options', {'options': updated})
        return {'saved': True, 'restart_required': True, 'revision': revision(updated)}


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass  # Never log request bodies, paths with query strings, or credentials.

        def authorized(self):
            supplied = self.headers.get('X-Professional-Token', '')
            return hmac.compare_digest(supplied, app.proxy_token)

        def respond(self, status, body, content_type='application/json', download=False):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="tailscale-diagnostics.json"')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.authorized():
                return self.respond(403, {'error': 'Open this dashboard through Home Assistant.'})
            path = urlsplit(self.path).path
            try:
                if path == '/api/session':
                    return self.respond(200, app.session())
                if path == '/api/status':
                    return self.respond(200, app.status())
                if path == '/api/diagnostics':
                    return self.respond(200, app.diagnostics(), download=True)
                assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                          '/style.css': ('style.css', 'text/css; charset=utf-8')}
                if path in assets:
                    filename, kind = assets[path]
                    return self.respond(200, (STATIC / filename).read_bytes(), kind)
                return self.respond(404, {'error': 'Not found.'})
            except OptionsError as error:
                return self.respond(503, {'error': str(error)})
            except OSError:
                return self.respond(503, {'error': 'The dashboard is temporarily unavailable.'})

        def do_POST(self):
            if not self.authorized() or not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), app.csrf):
                self.close_connection = True
                return self.respond(403, {'error': 'Refresh the dashboard and try again.'})
            if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                self.close_connection = True
                return self.respond(415, {'error': 'JSON requests are required.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    self.close_connection = True
                    return self.respond(413, {'error': 'Request size is invalid.'})
                self.connection.settimeout(10)
                body = json.loads(self.rfile.read(size))
                if self.path == '/api/setup':
                    return self.respond(200, app.save(body))
                if self.path == '/api/restart' and body == {'confirm': True}:
                    # Return the response before Supervisor stops this process.
                    def restart():
                        try:
                            app.api('POST', '/addons/self/restart')
                        except OptionsError:
                            pass  # UI detects lack of reconnect and offers manual restart.
                    timer = threading.Timer(1, restart)
                    timer.daemon = True
                    self.respond(202, {'restarting': True})
                    timer.start()
                    return
                return self.respond(404, {'error': 'Not found.'})
            except (OptionsError, ValueError, TypeError) as error:
                return self.respond(400, {'error': str(error) if isinstance(error, OptionsError) else 'Invalid setup request.'})
            except OSError:
                return self.respond(503, {'error': 'The request could not be completed.'})
    return Handler


def main():
    os.umask(0o077)
    RUNTIME.mkdir(mode=0o700, parents=True, exist_ok=True)
    token_path = RUNTIME / 'proxy-token'
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(48))
    port_path = RUNTIME / 'port'
    port = int(port_path.read_text()) if port_path.exists() else 0
    app = Dashboard(token_path.read_text())
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(app))
    server.daemon_threads = True
    port_path.write_text(str(server.server_port))
    # S6 starts nginx only once the dashboard's socket is bound and token is ready.
    try:
        os.write(3, b'\n')
        os.close(3)
    except OSError:
        pass
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
