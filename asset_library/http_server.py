import argparse
import hmac
import json
import os
import secrets
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .governance_api import governance_response
from .hardware_api import hardware_response
from .producer_api import producer_response
from .runtime import build_runtime


API_PREFIX = "/api/agent10"
MAX_REQUEST_BYTES = 20 * 1024 * 1024  # One bounded 12 MiB image, base64 plus JSON.
REQUEST_TIMEOUT_SECONDS = 10


class Agent10HttpApp:
    def __init__(self, runtime, control_token):
        self.runtime = runtime
        self.control_token = control_token

    def authorize(self, headers, client_host):
        if not _is_loopback(client_host):
            return _json_response(403, {"error": "loopback_required"})
        if not _has_control_token(headers, self.control_token):
            return _json_response(403, {"error": "control_authorization_required"})

    def dispatch(self, method, path, headers, body, client_host):
        denied = self.authorize(headers, client_host)
        if denied:
            return denied
        if len(body) > MAX_REQUEST_BYTES:
            return _json_response(413, {"error": "request_too_large"})
        try:
            text_body = body.decode("utf-8")
        except UnicodeDecodeError:
            return _json_response(400, {"error": "invalid_utf8"})
        parsed = urlsplit(path)
        route_path = parsed.path
        if not route_path.startswith(API_PREFIX):
            return _json_response(404, {"error": "not_found"})

        asset_path = "/api/asset-library" + route_path[len(API_PREFIX) :]
        if asset_path.startswith("/api/asset-library/governance"):
            status, response_headers, text = governance_response(
                method,
                asset_path,
                self.runtime.governance_service,
                mutation_authorized=True,
            )
            return status, response_headers, text.encode("utf-8")
        if asset_path.startswith("/api/asset-library/hardware"):
            return hardware_response(
                method,
                asset_path,
                body,
                self.runtime.hardware_service,
                parsed.query,
            )
        if asset_path.startswith("/api/asset-library/migrations/"):
            return _json_response(404, {"error": "not_found"})
        status, response_headers, text = producer_response(
            method,
            asset_path,
            text_body,
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
        def setup(self):
            self.request.settimeout(REQUEST_TIMEOUT_SECONDS)
            super().setup()

        def do_GET(self):
            self._dispatch()

        def do_POST(self):
            self._dispatch()

        def do_PUT(self):
            self._dispatch()

        def do_PATCH(self):
            self._dispatch()

        def do_DELETE(self):
            self._dispatch()

        def _dispatch(self):
            headers = {key.lower(): value for key, value in self.headers.items()}
            response = app.authorize(headers, self.client_address[0])
            if response is None:
                lengths = self.headers.get_all("content-length", [])
                raw_length = lengths[0] if lengths else "0"
                if len(lengths) > 1 or not raw_length.isascii() or not raw_length.isdigit() or "transfer-encoding" in headers:
                    response = _json_response(400, {"error": "invalid_content_length"})
                elif len(raw_length) > 10 or int(raw_length) > MAX_REQUEST_BYTES:
                    response = _json_response(413, {"error": "request_too_large"})
                else:
                    try:
                        length = int(raw_length)
                        deadline = time.monotonic() + REQUEST_TIMEOUT_SECONDS
                        chunks, remaining = [], length
                        while remaining:
                            timeout = deadline - time.monotonic()
                            if timeout <= 0:
                                raise TimeoutError("body deadline exceeded")
                            self.connection.settimeout(timeout)
                            chunk = self.rfile.read1(min(remaining, 65536))
                            if not chunk:
                                break
                            chunks.append(chunk)
                            remaining -= len(chunk)
                        body = b"".join(chunks)
                        response = (_json_response(400, {"error": "incomplete_body"}) if len(body) != length
                                    else app.dispatch(self.command, self.path, headers, body, self.client_address[0]))
                    except (socket.timeout, TimeoutError):
                        response = _json_response(408, {"error": "request_timeout"})
                    except Exception:
                        response = _json_response(500, {"error": "internal_error"})
            self._send_response(response)

        def _send_response(self, response):
            status, headers, response_body = response
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
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
    return hmac.compare_digest(supplied.encode("utf-8"), f"Bearer {expected}".encode("utf-8"))


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
