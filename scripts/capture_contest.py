#!/usr/bin/env python3
"""Capture the competition pages using the local Microsoft Edge in headless mode.

Used instead of Playwright on the Windows workstation that does the crawling:
no chromium download, no extra dependency, just the browser that ships with
Windows 11.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dom  # noqa: E402
import lib  # noqa: E402

BASE = lib.BASE

ROUTES = [
    ("home", "/"),
    ("theme-competation-index", "/#/theme-competation/index"),
    ("theme-competation-announcement", "/#/theme-competation/announcement"),
    ("theme-competation-resources", "/#/theme-competation/resources"),
    ("theme-competation-track-interaction", "/#/theme-competation/track/interaction"),
    ("theme-competation-track-cabin-theme", "/#/theme-competation/track/cabin-theme"),
    ("theme-competation-track-wallpaper", "/#/theme-competation/track/wallpaper"),
    ("theme-competation-works", "/#/theme-competation/works"),
]

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_edge() -> str | None:
    for candidate in EDGE_CANDIDATES:
        if os.path.exists(candidate):
            return candidate
    return None


def dump_dom(edge: str, url: str, profile: str, budget_ms: int = 20000) -> str:
    args = [
        edge,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        f"--user-data-dir={profile}",
        f"--virtual-time-budget={budget_ms}",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(args, capture_output=True, timeout=120)
    out = proc.stdout.decode("utf-8", "replace")
    if not out.strip() and proc.stderr:
        lib.log("   edge stderr: " + proc.stderr.decode("utf-8", "replace")[:300])
    return out


def screenshot(edge: str, url: str, profile: str, dest: str, width: int, height: int) -> bool:
    args = [
        edge,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        f"--user-data-dir={profile}",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        f"--virtual-time-budget=15000",
        f"--screenshot={dest}",
        url,
    ]
    try:
        subprocess.run(args, capture_output=True, timeout=150)
        return os.path.exists(dest) and os.path.getsize(dest) > 1000
    except Exception as exc:  # noqa: BLE001
        lib.log(f"   screenshot failed: {exc}")
        return False


def clean_html(raw: str) -> str:
    raw = raw.strip()
    # Edge's --dump-dom occasionally wraps the document in a JSON-ish string
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1].encode().decode("unicode_escape", "ignore")
    m = re.search(r"<html", raw, re.I)
    if m:
        raw = raw[m.start():]
    return raw


def main() -> int:
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "docs")
    cap = os.path.join(out, "contest", "captured")
    os.makedirs(cap, exist_ok=True)
    edge = find_edge()
    if not edge:
        lib.log("capture_contest: Microsoft Edge not found, skipping")
        return 0

    profile = os.path.join(tempfile.gettempdir(), "byd-capture-profile")
    summary = []
    for name, path in ROUTES:
        url = BASE + path
        lib.log(f"capture_contest: {url}")
        raw = dump_dom(edge, url, profile)
        if not raw.strip():
            lib.log("   empty DOM, skipped")
            continue
        html = clean_html(raw)
        lib.write_text(os.path.join(cap, name + ".html"), "<!doctype html>\n" + html)
        text = dom.text_of(dom.parse(html))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        lib.write_text(os.path.join(cap, name + ".txt"), text + "\n")
        summary.append({"name": name, "url": url, "chars": len(text)})

    if screenshot(edge, BASE + "/#/theme-competation/index", profile,
                  os.path.join(cap, "theme-competation-index.png"), 1440, 3200):
        summary.append({"name": "theme-competation-index.png", "url": BASE, "chars": 0})

    lib.write_json(os.path.join(cap, "index.json"), summary)
    lib.log(f"capture_contest: {len(summary)} artefacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
