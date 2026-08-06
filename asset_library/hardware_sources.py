"""Safe metadata and bounded content handling for one user-supplied URL."""

import hashlib
import ipaddress
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_REFERENCE_BYTES = 512 * 1024
MAX_REFERENCE_TEXT_CHARS = 120000
MAX_REFERENCE_CONTEXT_CHARS = 4000
MAX_REFERENCE_REDIRECTS = 3
REFERENCE_FETCH_TIMEOUT_SECONDS = 10


def validate_reference_url(raw_url):
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise ValueError("reference URL is required")
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("reference URL must be public HTTPS without credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "ip6-localhost"}:
        raise ValueError("reference URL must not target a private address")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_multicast):
        raise ValueError("reference URL must not target a private address")
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def parse_reference_input(value):
    """Extract the first HTTPS URL while retaining the user's bounded context."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError("reference input is required")
    match = re.search(r"https://[^\s<>()[\]{}]+", value, flags=re.IGNORECASE)
    if not match:
        raise ValueError("reference input must contain an HTTPS URL")
    raw_url = match.group(0).rstrip(".,;，。；）)")
    context = (value[:match.start()] + " " + value[match.end():]).strip()
    return {"url": validate_reference_url(raw_url), "context": context[:MAX_REFERENCE_CONTEXT_CHARS]}


def capture_reference(url, body, content_type):
    canonical = validate_reference_url(url)
    if not isinstance(body, bytes) or len(body) > MAX_REFERENCE_BYTES:
        raise ValueError("reference response exceeds the size limit")
    normalized_type = _content_type(content_type)
    if normalized_type not in {"text/html", "application/pdf"}:
        return {
            "url": canonical,
            "status": "link_only",
            "content_type": normalized_type,
            "content_sha256": _sha(body),
            "title": "",
            "body": "",
        }
    text = body.decode("utf-8", errors="replace")[:MAX_REFERENCE_TEXT_CHARS] if normalized_type == "text/html" else ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip()[:240] if title_match else ""
    return {
        "url": canonical,
        "status": "link_only",
        "content_type": normalized_type,
        "content_sha256": _sha(body),
        "title": title,
        "body": text,
    }


def fetch_reference(raw_url, opener=None, resolve_host=None):
    """Fetch one bounded public HTTPS reference after SSRF checks."""

    canonical = validate_reference_url(raw_url)
    resolver = resolve_host or _resolve_host
    _assert_public_host(canonical, resolver)
    active_opener = opener or build_opener(_SafeRedirectHandler(resolver))
    request = Request(
        canonical,
        headers={
            "Accept": "text/html, application/pdf;q=0.9, */*;q=0.1",
            "User-Agent": "Agent10-Hardware-Library/1.0",
        },
        method="GET",
    )
    with active_opener(request, timeout=REFERENCE_FETCH_TIMEOUT_SECONDS) as response:
        final_url = validate_reference_url(response.geturl() or canonical)
        _assert_public_host(final_url, resolver)
        body = response.read(MAX_REFERENCE_BYTES + 1)
        if len(body) > MAX_REFERENCE_BYTES:
            raise ValueError("reference response exceeds the size limit")
        captured = capture_reference(final_url, body, _response_content_type(response))
        if body:
            captured["status"] = "fetched"
        captured["retrieved_at"] = _now()
        return captured


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, resolve_host):
        super().__init__()
        self.resolve_host = resolve_host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirect_count = int(getattr(req, "_agent10_redirect_count", 0))
        if redirect_count >= MAX_REFERENCE_REDIRECTS:
            raise ValueError("reference URL exceeded the redirect limit")
        target = urljoin(req.full_url, newurl)
        canonical = validate_reference_url(target)
        _assert_public_host(canonical, self.resolve_host)
        redirected = super().redirect_request(req, fp, code, msg, headers, canonical)
        if redirected is not None:
            redirected._agent10_redirect_count = redirect_count + 1
        return redirected


def _response_content_type(response):
    headers = getattr(response, "headers", {})
    if hasattr(headers, "get_content_type"):
        return headers.get_content_type()
    return headers.get("Content-Type", "application/octet-stream")


def _content_type(value):
    return str(value or "application/octet-stream").split(";", 1)[0].strip().lower()


def _resolve_host(host):
    return [item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)]


def _assert_public_host(url, resolver):
    host = urlsplit(url).hostname
    if not host:
        raise ValueError("reference URL must have a hostname")
    for value in resolver(host):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            continue
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("reference URL must not resolve to a private address")


def _sha(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
