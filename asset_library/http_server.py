import argparse
import hmac
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .governance_api import governance_response
from .producer_api import producer_response
from .runtime import build_runtime


API_PREFIX = "/api/agent10"


class Agent10HttpApp:
    def __init__(self, runtime, control_token):
        self.runtime = runtime
        self.control_token = control_token

    def dispatch(self, method, path, headers, body, client_host):
        if not _is_loopback(client_host):
            return _json_response(403, {"error": "loopback_required"})
        if not _has_control_token(headers, self.control_token):
            return _json_response(403, {"error": "control_authorization_required"})
        if not path.startswith(API_PREFIX):
            return _json_response(404, {"error": "not_found"})

        asset_path = "/api/asset-library" + path[len(API_PREFIX) :]
        if asset_path.startswith("/api/asset-library/governance"):
            status, response_headers, text = governance_response(
                method,
                asset_path,
                self.runtime.governance_service,
                mutation_authorized=True,
            )
            return status, response_headers, text.encode("utf-8")
        if asset_path.startswith("/api/asset-library/migrations/"):
            return _json_response(404, {"error": "not_found"})
        status, response_headers, text = producer_response(
            method,
            asset_path,
            body.decode("utf-8"),
            self.runtime.producer_service,
            migration_authorized=False,
        )
        return status, response_headers, text.encode("utf-8")


def ensure_control_token(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if _is_control_token(token):
            os.chmod(path, 0o600)
            return token
        raise ValueError("existing Agent10 control token is invalid")
    token = secrets.token_hex(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return token


def create_http_server(runtime, control_token, host="127.0.0.1", port=8010):
    if not _is_loopback(host):
        raise ValueError("Agent10 HTTP server must bind to a loopback host")
    app = Agent10HttpApp(runtime, control_token)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_PUT(self):
            self._dispatch()

        def do_DELETE(self):
            self._dispatch()

        def _dispatch(self):
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length) if length else b""
            status, headers, response_body = app.dispatch(
                self.command,
                self.path.split("?", 1)[0],
                {key.lower(): value for key, value in self.headers.items()},
                body,
                self.client_address[0],
            )
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            if response_body:
                self.wfile.write(response_body)

        def log_message(self, format, *args):
            return

    return ThreadingHTTPServer((host, port), Handler)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--control-token-file", required=True)
    args = parser.parse_args(argv)
    runtime = build_runtime()
    token = ensure_control_token(args.control_token_file)
    server = create_http_server(runtime, token, host=args.host, port=args.port)
    server.serve_forever()


def _has_control_token(headers, expected):
    supplied = headers.get("authorization", "")
    return hmac.compare_digest(supplied, f"Bearer {expected}")


def _is_control_token(value):
    if len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _is_loopback(host):
    return host in {"127.0.0.1", "::1", "localhost"}


def _json_response(status, payload):
    return (
        status,
        {"content-type": "application/json; charset=utf-8"},
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    )


if __name__ == "__main__":
    main()
