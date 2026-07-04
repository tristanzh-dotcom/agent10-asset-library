import json
import unittest

from asset_library.obsidian_rest import ObsidianRestClient


class FakeTransport:
    def __init__(self):
        self.requests = []

    def __call__(self, method, url, headers, body, timeout, context):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "body": body,
                "timeout": timeout,
                "context": context,
            }
        )
        path = url.removeprefix("http://obsidian.local")
        if method == "GET" and path == "/":
            return json.dumps({"status": "OK", "authenticated": True}).encode("utf-8")
        if method == "GET" and path == "/vault/01_Agents%2FAgent06%2Fnote.md":
            return b"# Note\n"
        if method == "PUT" and path == "/vault/01_Agents%2FAgent10%2Fnew.md":
            return b""
        if method == "GET" and path == "/tags/":
            return json.dumps({"tags": [{"name": "agent/agent06", "count": 1}]}).encode("utf-8")
        if method == "POST" and path == "/mcp/":
            payload = {
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {"listChanged": True}},
                },
                "jsonrpc": "2.0",
                "id": 1,
            }
            return f"event: message\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
        raise AssertionError(f"unexpected request {method} {url}")


class ObsidianRestClientTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.client = ObsidianRestClient(
            "http://obsidian.local",
            "secret-token",
            verify_tls=False,
            transport=self.transport,
        )

    def test_status_sends_bearer_auth(self):
        status = self.client.status()

        self.assertEqual(status["status"], "OK")
        self.assertEqual(self.transport.requests[-1]["headers"]["Authorization"], "Bearer secret-token")

    def test_read_note_encodes_vault_path_segments_as_one_path_parameter(self):
        note = self.client.read_note("01_Agents/Agent06/note.md")

        self.assertEqual(note, "# Note\n")
        self.assertEqual(
            self.transport.requests[-1]["url"],
            "http://obsidian.local/vault/01_Agents%2FAgent06%2Fnote.md",
        )

    def test_write_note_puts_markdown(self):
        self.client.write_note("01_Agents/Agent10/new.md", "# New\n")

        request = self.transport.requests[-1]
        self.assertEqual(request["method"], "PUT")
        self.assertEqual(request["headers"]["Content-Type"], "text/markdown; charset=utf-8")
        self.assertEqual(request["body"], b"# New\n")

    def test_list_tags(self):
        tags = self.client.list_tags()

        self.assertEqual(tags["tags"][0]["name"], "agent/agent06")

    def test_mcp_initialize_parses_event_stream_response(self):
        response = self.client.mcp_initialize()

        self.assertEqual(response["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("application/json", self.transport.requests[-1]["headers"]["Accept"])
        self.assertIn("text/event-stream", self.transport.requests[-1]["headers"]["Accept"])


if __name__ == "__main__":
    unittest.main()
