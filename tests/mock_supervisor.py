"""Supervisor fixture for an isolated, network-disabled container startup test."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
options = json.loads(Path('/data/options.json').read_text())
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)
    def do_GET(self):
        if self.path in ('/addons/self/info', '/apps/self/info'):
            data = {'options': options, 'ip_address':'127.0.0.1','ingress_port':8099,
                    'network': {'41641/udp':None},'ports':{'41641/udp':None},'slug':'local_tailscale_professional'}
        elif self.path == '/dns/info':
            data = {'locals':[],'servers':[],'fallback':True,'host':'127.0.0.1'}
        elif self.path in ('/info','/host/info'):
            data = {'hostname':'smoke-homeassistant'}
        elif self.path == '/core/info':
            data = {'ssl':False,'port':8123}
        else:
            data = {}
        self.reply(data)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
        if self.path.endswith('/options') and 'options' in body:
            options.clear(); options.update(body['options'])
        self.reply({})
    def reply(self,data):
        payload=json.dumps({'result':'ok','data':data}).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
ThreadingHTTPServer(('127.0.0.1',80),Handler).serve_forever()
