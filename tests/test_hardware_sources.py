import unittest
import os
from unittest.mock import patch
from urllib.request import OpenerDirector
from urllib.request import Request
from asset_library import hardware_sources
from asset_library.hardware_sources import fetch_reference, parse_reference_input, validate_reference_url, capture_reference


class _FakeResponse:
    def __init__(self, body, url="https://vendor.example/manual"):
        self.body = body
        self.url = url
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.code = 200
        self.reason = "OK"
        self.msg = "OK"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.url

    def read(self, _limit):
        return self.body

    def info(self):
        return self.headers


class HardwareSourcesTests(unittest.TestCase):
    def test_rejects_non_https_and_private_hosts(self):
        for url in ("http://vendor.example/manual", "https://127.0.0.1/manual", "https://user:pass@vendor.example/manual", "https://224.0.0.1/manual"):
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
            resolve_host=lambda _host: ["8.8.8.8"],
        )

        self.assertEqual(result["status"], "fetched")
        self.assertIn("90 x 25 mm", result["body"])
        self.assertEqual(calls[0][0], "https://vendor.example/manual")
        self.assertEqual(calls[0][1], 10)

    def test_empty_invalid_and_private_dns_fail_before_transport(self):
        for answers in ([], ["bad-address"], ["8.8.8.8", "127.0.0.1"], ["224.0.0.1"]):
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                fetch_reference("https://vendor.example/manual", opener=lambda *_args, **_kwargs: self.fail("unsafe transport"), resolve_host=lambda _host: answers)

    def test_default_opener_uses_open_and_disables_environment_proxies(self):
        with patch.object(OpenerDirector, "open", return_value=_FakeResponse(b"<title>Safe</title>")) as opened:
            result = fetch_reference("https://vendor.example/manual", resolve_host=lambda _host: ["8.8.8.8"])
        self.assertEqual(result["title"], "Safe")
        self.assertEqual(opened.call_count, 1)

    def test_default_transport_retains_host_and_never_resolves_again_after_validation(self):
        calls = []
        answers = iter([["8.8.8.8"], ["127.0.0.1"]])
        def request(connection, method, selector, body, headers, **_kwargs):
            calls.append((connection.host, connection.addresses, connection._tunnel_host, headers.get("Host")))
        with patch.dict(os.environ, {"https_proxy": "http://127.0.0.1:9999"}), patch.object(hardware_sources._PinnedHTTPSConnection, "request", request), patch.object(hardware_sources._PinnedHTTPSConnection, "getresponse", return_value=_FakeResponse(b"<title>Safe</title>")):
            result = fetch_reference("https://vendor.example/manual", resolve_host=lambda _host: next(answers))
        self.assertEqual(result["title"], "Safe")
        self.assertEqual(calls, [("vendor.example", ("8.8.8.8",), None, "vendor.example")])
        self.assertEqual(next(answers), ["127.0.0.1"])

    def test_redirect_revalidates_and_binds_its_own_address_set(self):
        handler = hardware_sources._SafeRedirectHandler(lambda host: ["8.8.4.4"] if host == "other.example" else ["127.0.0.1"])
        redirected = handler.redirect_request(Request("https://vendor.example/manual"), None, 302, "Found", {}, "https://other.example/manual")
        self.assertEqual(redirected._agent10_addresses, ("8.8.4.4",))
        with self.assertRaises(ValueError):
            handler.redirect_request(redirected, None, 302, "Found", {}, "https://private.example/")

    def test_https_transport_pins_validated_ip_but_preserves_tls_hostname(self):
        connected = []
        wrapped = []
        class Context:
            verify_mode = 2
            check_hostname = True
            def wrap_socket(self, sock, server_hostname):
                wrapped.append(server_hostname)
                return sock
        with patch.object(hardware_sources.socket, "create_connection", side_effect=lambda address, *_args, **_kwargs: connected.append(address) or object()):
            connection = hardware_sources._PinnedHTTPSConnection("vendor.example", ("8.8.8.8",), context=Context())
            connection.connect()
        self.assertEqual(connected, [("8.8.8.8", 443)])
        self.assertEqual(wrapped, ["vendor.example"])

    def test_parse_reference_input_extracts_url_and_retains_bounded_context(self):
        result = parse_reference_input("https://vendor.example/manual  官方说明书；厂商 Demo；版本 1.2；发布日期 2026-08-01")

        self.assertEqual(result["url"], "https://vendor.example/manual")
        self.assertIn("官方说明书", result["context"])
        self.assertIn("版本 1.2", result["context"])


if __name__ == "__main__":
    unittest.main()
