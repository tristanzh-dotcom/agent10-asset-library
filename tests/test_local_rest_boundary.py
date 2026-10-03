import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from asset_library.obsidian_rest import ObsidianRestClient, ObsidianRestError


class LocalRestBoundaryTests(unittest.TestCase):
    def serve(self, handler):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f'http://127.0.0.1:{server.server_port}'

    def test_non_loopback_or_ambiguous_base_is_rejected(self):
        for url in ['https://example.invalid', 'http://127.0.0.1@evil.invalid', 'http://127.0.0.1/api', 'http://127.0.0.1?token=x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                ObsidianRestClient(url, 'SYNTHETIC')

    def test_redirect_is_rejected_before_credentials_reach_second_server(self):
        received = []
        class Destination(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                received.append(self.headers.get('Authorization'))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        destination = self.serve(Destination)
        class Redirect(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(302); self.send_header('Location', destination); self.end_headers()
        url = self.serve(Redirect)
        with self.assertRaises(ObsidianRestError):
            ObsidianRestClient(url, 'SYNTHETIC').status()
        self.assertEqual([], received)

    def test_environment_proxy_does_not_receive_local_credentials(self):
        proxy_requests = []
        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                proxy_requests.append(self.headers.get('Authorization'))
                self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        proxy = self.serve(Proxy)
        class Origin(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({'status': 'local'}).encode())
        url = self.serve(Origin)
        with patch.dict('os.environ', {'http_proxy': proxy, 'HTTP_PROXY': proxy, 'no_proxy': '', 'NO_PROXY': ''}), patch('urllib.request._opener', None):
            self.assertEqual({'status': 'local'}, ObsidianRestClient(url, 'SYNTHETIC').status())
        self.assertEqual([], proxy_requests)
