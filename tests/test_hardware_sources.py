import unittest
from asset_library.hardware_sources import fetch_reference, parse_reference_input, validate_reference_url, capture_reference


class _FakeResponse:
    def __init__(self, body, url="https://vendor.example/manual"):
        self.body = body
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, _limit):
        return self.body


class HardwareSourcesTests(unittest.TestCase):
    def test_rejects_non_https_and_private_hosts(self):
        for url in ("http://vendor.example/manual", "https://127.0.0.1/manual", "https://user:pass@vendor.example/manual"):
            with self.assertRaises(ValueError):
                validate_reference_url(url)

    def test_capture_keeps_link_when_document_has_no_hardware_candidate(self):
        result = capture_reference("https://vendor.example/sdk", b"SDK protocol documentation", "text/html")
        self.assertEqual(result["status"], "link_only")
        self.assertEqual(result["url"], "https://vendor.example/sdk")
        self.assertNotIn("/", result["body"][:1])

    def test_fetch_reference_reads_bounded_html_after_public_https_validation(self):
        calls = []

        def opener(request, timeout):
            calls.append((request.full_url, timeout, request.headers.get("User-agent")))
            return _FakeResponse(b"<html><title>Board manual</title><p>90 x 25 mm</p></html>")

        result = fetch_reference(
            "https://vendor.example/manual",
            opener=opener,
            resolve_host=lambda _host: [],
        )

        self.assertEqual(result["status"], "fetched")
        self.assertIn("90 x 25 mm", result["body"])
        self.assertEqual(calls[0][0], "https://vendor.example/manual")
        self.assertEqual(calls[0][1], 10)

    def test_parse_reference_input_extracts_url_and_retains_bounded_context(self):
        result = parse_reference_input("https://vendor.example/manual  官方说明书；厂商 Demo；版本 1.2；发布日期 2026-08-01")

        self.assertEqual(result["url"], "https://vendor.example/manual")
        self.assertIn("官方说明书", result["context"])
        self.assertIn("版本 1.2", result["context"])


if __name__ == "__main__":
    unittest.main()
