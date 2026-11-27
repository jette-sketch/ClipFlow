"""ClipFlow read-only dashboard DEMO server. Loopback ONLY; no production auth or integrations."""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / 'public'
FIXTURE = ROOT / 'fixtures' / 'demo.json'
ALLOWED_STATIC = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/index.html': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
}
HEADERS = {
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'",
}

class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, data: bytes, content_type: str):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        for k,v in HEADERS.items(): self.send_header(k,v)
        self.end_headers()
        if self.command != 'HEAD': self.wfile.write(data)

    def do_GET(self):
        route = urlsplit(self.path).path
        if route == '/api/v1/dashboard':
            raw = FIXTURE.read_bytes()
            self._send(200,raw,'application/json; charset=utf-8')
        elif route in ALLOWED_STATIC:
            path, mime = ALLOWED_STATIC[route]
            self._send(200,(PUBLIC / path).read_bytes(),mime)
        else:
            self._send(404,b'{"error":"not_found"}','application/json; charset=utf-8')

    def do_HEAD(self): self.do_GET()
    def do_POST(self): self._send(405,b'{"error":"read_only"}','application/json; charset=utf-8')
    def do_DELETE(self): self.do_POST()
    def do_PUT(self): self.do_POST()
    def do_PATCH(self): self.do_POST()
    def do_OPTIONS(self): self._send(405,b'{"error":"read_only"}','application/json; charset=utf-8')
    def log_message(self, format, *args): pass


def make_server(port=8765):
    return ThreadingHTTPServer(('127.0.0.1', int(port)), Handler)

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='ClipFlow local dashboard DEMO (synthetic data; loopback only)')
    p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    server = make_server(args.port)
    print(f'ClipFlow DEMO on http://127.0.0.1:{server.server_address[1]} (synthetic data only)')
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
