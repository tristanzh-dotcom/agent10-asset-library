import json
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ObsidianRestError(RuntimeError):
    pass


class ObsidianRestClient:
    def __init__(self, base_url, api_key, verify_tls=False, timeout=5, transport=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport
        self.context = None
        if self.base_url.startswith("https://") and not verify_tls:
            self.context = ssl._create_unverified_context()

    def status(self):
        return self._request_json("GET", "/")

    def read_note(self, path):
        response = self._request("GET", f"/vault/{self._encode_vault_path(path)}")
        return response.decode("utf-8")

    def write_note(self, path, markdown):
        data = markdown.encode("utf-8")
        self._request(
            "PUT",
            f"/vault/{self._encode_vault_path(path)}",
            body=data,
            headers={"Content-Type": "text/markdown; charset=utf-8"},
        )

    def list_tags(self):
        return self._request_json("GET", "/tags/")

    def mcp_initialize(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "agent10-asset-library", "version": "0.1.0"},
            },
        }
        body = self._request(
            "POST",
            "/mcp/",
            body=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        ).decode("utf-8")
        return _parse_event_stream_json(body)

    def _request_json(self, method, path, body=None, headers=None):
        response = self._request(method, path, body=body, headers=headers)
        return json.loads(response.decode("utf-8"))

    def _request(self, method, path, body=None, headers=None):
        request_headers = {"Authorization": f"Bearer {self.api_key}"}
        if headers:
            request_headers.update(headers)
        if self.transport is not None:
            return self.transport(method, self.base_url + path, request_headers, body, self.timeout, self.context)
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=self.timeout, context=self.context) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ObsidianRestError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ObsidianRestError(f"{method} {path} failed: {exc.reason}") from exc

    @staticmethod
    def _encode_vault_path(path):
        return quote(path, safe="")


def _parse_event_stream_json(body):
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise ObsidianRestError("MCP response did not include a data event")
