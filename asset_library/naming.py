from datetime import timezone, timedelta
import re
import secrets


UTC_PLUS_8 = timezone(timedelta(hours=8))
UNSAFE_TITLE_CHARS = re.compile(r'[/\\:*?"<>|\x00-\x1f]+')
DASH_RUN = re.compile(r"-+")


def generate_asset_id(now=None, token_hex=None):
    if now is None:
        from datetime import datetime

        now = datetime.now(timezone.utc)
    if token_hex is None:
        token_hex = secrets.token_hex
    date_part = now.astimezone(UTC_PLUS_8).strftime("%Y%m%d")
    random_part = token_hex(4)
    return f"ast_{date_part}_{random_part.lower()[:8]}"


def sanitize_short_title(title, asset_id):
    raw = "" if title is None else str(title)[:50]
    safe = UNSAFE_TITLE_CHARS.sub("-", raw)
    safe = re.sub(r"\s*-\s*", "-", safe)
    safe = DASH_RUN.sub("-", safe)
    safe = safe.strip(" -.\t\r\n")
    if safe in ("", ".", ".."):
        return asset_id
    return safe
