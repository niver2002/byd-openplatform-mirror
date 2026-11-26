"""Shared helpers for the BYD Open Platform mirror crawler."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://openplatform.byd.com"
CDN = "openplatform-cdn.byd.com"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Referer": BASE + "/",
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
}

_CTX = ssl.create_default_context()
_LOCK = threading.Lock()
STATS = {"http_ok": 0, "http_fail": 0, "retries": 0, "bytes": 0}


def log(msg: str) -> None:
    with _LOCK:
        print(msg, flush=True)


def _decode_body(raw: bytes, encoding: str) -> bytes:
    enc = (encoding or "").lower()
    if enc == "gzip":
        return gzip.decompress(raw)
    if enc == "deflate":
        try:
            import zlib

            return zlib.decompress(raw)
        except Exception:
            return zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw


_SAFE_PATH = "/%:@!$&'()*+,;=~"
_SAFE_QUERY = "=&%:/?@!$'()*+,;~-._"


def _safe_url(url: str) -> str:
    """Percent-encode non-ASCII characters so urllib can send the request.

    Several attachments live under Chinese file names (e.g.
    /dop/static/theme/template/主题商店设计模板.sketch) which urllib refuses to
    encode on its own.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.netloc.isascii() and parts.path.isascii() and parts.query.isascii():
        return url
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe=_SAFE_PATH),
            urllib.parse.quote(parts.query, safe=_SAFE_QUERY),
            parts.fragment,
        )
    )


def http_get(url: str, retries: int = 4, timeout: int = 60) -> bytes:
    url = _safe_url(url)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                raw = r.read()
                body = _decode_body(raw, r.headers.get("Content-Encoding", ""))
            with _LOCK:
                STATS["http_ok"] += 1
                STATS["bytes"] += len(body)
            return body
        except Exception as exc:  # noqa: BLE001
            last = exc
            with _LOCK:
                STATS["retries"] += 1
            time.sleep(1.2 * (attempt + 1))
    with _LOCK:
        STATS["http_fail"] += 1
    raise last  # type: ignore[misc]


def api_post(path: str, payload: dict, retries: int = 4) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(retries):
        try:
            hdrs = dict(HEADERS)
            hdrs["Content-Type"] = "application/json"
            req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                raw = r.read()
                body = _decode_body(raw, r.headers.get("Content-Encoding", ""))
            with _LOCK:
                STATS["http_ok"] += 1
            return json.loads(body.decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            with _LOCK:
                STATS["retries"] += 1
            time.sleep(1.2 * (attempt + 1))
    with _LOCK:
        STATS["http_fail"] += 1
    raise last  # type: ignore[misc]


def api_get(path: str, retries: int = 4) -> dict:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(BASE + path, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
                raw = r.read()
                body = _decode_body(raw, r.headers.get("Content-Encoding", ""))
            with _LOCK:
                STATS["http_ok"] += 1
            return json.loads(body.decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001
            last = exc
            with _LOCK:
                STATS["retries"] += 1
            time.sleep(1.2 * (attempt + 1))
    with _LOCK:
        STATS["http_fail"] += 1
    raise last  # type: ignore[misc]


def doc_tree(document_type: int) -> list:
    res = api_post(
        "/api/document-portal/document/portal/getUpDocument", {"documentType": document_type}
    )
    return res.get("result") or []


def doc_content(doc_id: int) -> str:
    res = api_get(f"/api/document-portal/document/portal/getUpDocumentContent?id={doc_id}")
    return res.get("result") or ""


def http_head_size(url: str, timeout: int = 30) -> int | None:
    """Best-effort Content-Length probe; None when the server will not say."""
    try:
        req = urllib.request.Request(_safe_url(url), headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            raw = r.headers.get("Content-Length")
            return int(raw) if raw and raw.isdigit() else None
    except Exception:  # noqa: BLE001
        return None


def sha1(text: str, n: int = 8) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:n]


_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def ascii_slug(text: str, fallback: str = "item") -> str:
    """Very small transliteration: keep ascii alnum, else fall back to id."""
    low = text.lower()
    low = (
        low.replace("api", "api")
        .replace("&", " and ")
        .replace("/", "-")
        .replace(" ", "-")
    )
    out = _SLUG_STRIP.sub("-", low).strip("-")
    return out or fallback


DOWNLOAD_EXTS = {
    "jar", "zip", "rar", "7z", "gz", "tar", "sketch", "pix", "psd", "ai", "fig",
    "xlsx", "xls", "csv", "docx", "doc", "pdf", "pptx", "ppt", "apk", "aar", "so",
}

MEDIA_EXTS = {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "mp4", "webm", "mov", "mp3", "wav"}

VIDEO_EXTS = {"mp4", "webm", "mov", "m4v", "avi", "mkv"}


def ext_of(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    _, ext = os.path.splitext(path)
    return ext.lower().lstrip(".")


def clean_url(url: str) -> str:
    """Drop the expiring auth_key / signature query strings from CDN links."""
    p = urllib.parse.urlparse(url)
    if p.netloc.endswith("byd.com"):
        return urllib.parse.urlunparse((p.scheme, p.netloc, p.path, "", "", ""))
    return url


def safe_filename(url: str, original_name: str | None = None) -> str:
    """Readable, filesystem-safe filename that still works as a URL.

    Keeps letters/digits (including CJK, so 主题商店设计模板 survives) and gives
    every file a short content-independent hash suffix to avoid collisions.
    """
    name = original_name or urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    base, ext = os.path.splitext(name)
    ext = ext.lower()
    cleaned = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in base)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    if not cleaned:
        cleaned = "file"
    return f"{cleaned[:60]}-{sha1(url, 6)}{ext}"


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path: str, obj) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def human_size(num: int) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if num < step:
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= step
    return f"{num:.1f} TB"
