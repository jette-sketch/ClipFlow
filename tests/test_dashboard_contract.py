"""No remote calls or account access: dashboard contract tests use synthetic fixtures only."""
from __future__ import annotations
import http.client
import json
import sys
from pathlib import Path
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'dashboard'))
from server import make_server  # noqa: E402


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = make_server(0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, target):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        c.request(method, target)
        r = c.getresponse()
        status, headers, body = r.status, dict(r.getheaders()), r.read()
        c.close()
        return status, headers, body

    def test_local_only_listener(self):
        self.assertEqual(self.httpd.server_address[0], '127.0.0.1')

    def test_demo_response_never_claims_connected(self):
        status, _, body = self.request('GET', '/api/v1/dashboard')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['mode'], 'synthetic_demo')
        self.assertIs(data['connected'], False)
        for key in ('trends','jobs','uploads','retention','incidents','systems'):
            self.assertTrue(data[key])

    def test_index_and_js_available(self):
        for path, phrase in [('/', b'CLIPFLOW'),('/app.js', b'synthetic_demo'),('/styles.css', b'.sidebar')]:
            status, _, body = self.request('GET', path)
            self.assertEqual(status, 200)
            self.assertIn(phrase.lower(), body.lower())

    def test_mutations_are_blocked(self):
        for method in ('POST','PUT','PATCH','DELETE'):
            status, _, body = self.request(method, '/api/v1/dashboard')
            self.assertEqual(status, 405)
            self.assertIn(b'read_only', body)

    def test_path_traversal_is_not_served(self):
        for path in ('/.env','/server.py','/../.env','/fixtures/demo.json'):
            status, _, _ = self.request('GET', path)
            self.assertEqual(status, 404)

    def test_response_security_headers(self):
        _, headers, _ = self.request('GET', '/')
        self.assertEqual(headers.get('X-Frame-Options'), 'DENY')
        self.assertIn("default-src 'self'", headers.get('Content-Security-Policy',''))
        self.assertEqual(headers.get('Cache-Control'),'no-store')

    def test_head_no_body(self):
        status, _, body = self.request('HEAD','/api/v1/dashboard')
        self.assertEqual(status,200)
        self.assertEqual(body, b'')


if __name__ == '__main__': unittest.main()
