#!/usr/bin/env python3
"""Render the competition pages in headless Chromium and archive what a real
browser sees: DOM snapshot, visible text, full-page screenshot and the network
log (which documents every XHR the page makes).

Runs only when Playwright + Chromium are available; otherwise it exits 0 and the
mirror still works from the API data alone.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    ("theme-competation-register", "/#/theme-competation/register"),
]

MAX_SHOT_HEIGHT = 14000


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", name)


def main() -> int:
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "docs")
    cap = os.path.join(out, "contest", "captured")
    os.makedirs(cap, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        lib.log(f"render_site: playwright unavailable ({exc}); skipping browser capture")
        return 0

    summary = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            for name, path in ROUTES:
                page = ctx.new_page()
                netlog: list[dict] = []

                def on_response(resp):
                    try:
                        ct = resp.headers.get("content-type", "")
                        if "json" in ct and "byd.com" in resp.url:
                            netlog.append(
                                {"url": resp.url, "status": resp.status, "contentType": ct,
                                 "body": resp.text()[:20000]}
                            )
                    except Exception:  # noqa: BLE001
                        pass

                page.on("response", on_response)
                url = BASE + path
                lib.log(f"render_site: {url}")
                try:
                    page.goto(url, wait_until="networkidle", timeout=90000)
                except Exception as exc:  # noqa: BLE001
                    lib.log(f"   goto warning: {exc}")
                page.wait_for_timeout(2500)
                try:
                    page.mouse.wheel(0, 20000)
                    page.wait_for_timeout(1500)
                    page.mouse.wheel(0, -20000)
                    page.wait_for_timeout(800)
                except Exception:  # noqa: BLE001
                    pass

                lib.write_text(os.path.join(cap, name + ".html"),
                               "<!doctype html>\n<meta charset=\"utf-8\">\n" + page.content())
                text = page.inner_text("body")
                lib.write_text(os.path.join(cap, name + ".txt"), text.strip() + "\n")
                lib.write_json(os.path.join(cap, name + ".netlog.json"), netlog)
                try:
                    height = page.evaluate("Math.min(document.body.scrollHeight, %d)" % MAX_SHOT_HEIGHT)
                    page.set_viewport_size({"width": 1440, "height": max(900, min(int(height), MAX_SHOT_HEIGHT))})
                    page.wait_for_timeout(600)
                    page.screenshot(path=os.path.join(cap, name + ".png"), full_page=False)
                except Exception as exc:  # noqa: BLE001
                    lib.log(f"   screenshot warning: {exc}")
                summary.append({"name": name, "url": url, "chars": len(text), "xhr": len(netlog)})
                page.close()
            browser.close()
    except Exception as exc:  # noqa: BLE001
        lib.log(f"render_site: capture failed ({exc}); continuing without browser snapshots")
        return 0

    lib.write_json(os.path.join(cap, "index.json"), summary)
    lib.log(f"render_site: captured {len(summary)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
