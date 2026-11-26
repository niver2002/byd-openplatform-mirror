#!/usr/bin/env python3
"""Mirror the BYD Open Platform documentation, API library and contest material.

Everything is fetched from the public endpoints behind openplatform.byd.com and
written into a self-contained static site (default: ./docs) with all images,
videos and downloadable attachments stored locally, so the result can be
published as-is via GitHub Pages.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import sys
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dom  # noqa: E402
import lib  # noqa: E402
from page import CSS, SITE_TITLE, esc, page  # noqa: E402

BASE = lib.BASE
SECTIONS = [
    (1, "dev", "开发者文档", "开发者注册、AIoT、应用分发、主题商店、平台协议等全量官方文档"),
    (2, "protocol", "协议规范", "软件开发协议与硬件接口规范（直连、云云对接、OTA、生态硬件接口）"),
    (3, "api", "API 库", "车机开放 API（车身、空调、充电、门锁、雷达等 21 类接口定义）"),
]
SECTION_LABEL = {slug: ("API" if slug == "api" else "文档") for _, slug, _, _ in SECTIONS}


# --------------------------------------------------------------------------- plan
def flatten(nodes: list, trail: list[str]) -> list[dict]:
    out = []
    for n in nodes:
        name = (n.get("name") or "").strip()
        path = trail + ([name] if name else [])
        if n.get("children"):
            out.extend(flatten(n["children"], path))
        else:
            out.append({"id": n["id"], "name": name or f"doc-{n['id']}", "trail": path})
    return out


def slug_for(section: str, doc: dict) -> str:
    """Readable, stable page name: <doc id>-<sanitised title>."""
    name = re.sub(r"[\\/:*?\"<>|#%&{}$!'@+`=,;]+", "", doc["name"]).strip()
    name = re.sub(r"\s+", "-", name)[:60].strip("-.") or "doc"
    return f"{doc['id']}-{name}"


# --------------------------------------------------------------------------- assets
class Assets:
    """Registry that maps remote asset URLs to mirrored local paths.

    CDN links carry an expiring ``auth_key`` signature which must be sent when
    downloading, but must not leak into committed file names or HTML, so the
    signed URL is kept only in ``fetch``.
    """

    def __init__(self, root: str, max_bytes: int, dry: bool, max_video_bytes: int = 0,
                 budget_bytes: int = 0):
        self.root = root
        self.max_bytes = max_bytes
        self.max_video_bytes = max_video_bytes or max_bytes
        self.budget_bytes = budget_bytes
        self.dry = dry
        self.map: dict[str, str] = {}          # cleaned url -> path relative to site root
        self.fetch: dict[str, str] = {}        # cleaned url -> signed url to download
        self.original: dict[str, str] = {}     # cleaned url -> original file name
        self.size: dict[str, int] = {}
        self.skipped: list[dict] = []
        self.down: set[str] = set()

    def _target(self, clean_url: str) -> str:
        ext = lib.ext_of(clean_url)
        bucket = "downloads" if ext in lib.DOWNLOAD_EXTS else "assets"
        return f"{bucket}/{lib.safe_filename(clean_url)}"

    def register(self, raw_url: str) -> str | None:
        raw = (raw_url or "").strip()
        if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            return None
        full = urllib.parse.urljoin(BASE + "/", raw)
        parsed = urllib.parse.urlparse(full)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.path or parsed.path == "/":
            return None  # SPA route, not a file
        if parsed.netloc and not parsed.netloc.endswith("byd.com"):
            return full  # keep third-party links pointing at the origin
        clean = lib.clean_url(full)
        if clean in self.map:
            return self.map[clean]
        rel = self._target(clean)
        self.map[clean] = rel
        self.fetch[clean] = full
        self.original[clean] = urllib.parse.unquote(os.path.basename(parsed.path))
        if not self.dry:
            self.down.add(clean)
        return rel

    def fetch_all(self, jobs: int) -> None:
        if self.dry or not self.down:
            return
        os.makedirs(os.path.join(self.root, "assets"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "downloads"), exist_ok=True)
        todo = sorted(self.down)

        def cap_for(url: str) -> int:
            return self.max_video_bytes if lib.ext_of(url) in lib.VIDEO_EXTS else self.max_bytes

        # 1. probe sizes so cheap files are fetched first and huge videos skipped
        lib.log(f"  probing {len(todo)} asset sizes …")
        sizes: dict[str, int | None] = {}
        with ThreadPoolExecutor(max_workers=min(jobs * 2, 16)) as ex:
            for url, size in zip(todo, ex.map(lib.http_head_size, todo)):
                sizes[url] = size

        plan: list[str] = []
        for url in sorted(todo, key=lambda u: (lib.ext_of(u) in lib.VIDEO_EXTS, sizes[u] or 0)):
            known = sizes[url]
            if known is not None and known > cap_for(url):
                self.skipped.append(
                    {
                        "url": url,
                        "reason": f"超过单文件上限 {lib.human_size(cap_for(url))}",
                        "size": known,
                        "localFallback": self._remote_fallback(url),
                    }
                )
                continue
            plan.append(url)

        lib.log(f"  downloading {len(plan)} assets (skipped {len(self.skipped)} oversized) …")
        used = 0
        done = 0
        lock = threading.Lock()

        def one(url: str) -> None:
            nonlocal used
            rel = self.map[url]
            dest = os.path.join(self.root, rel)
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                existing = os.path.getsize(dest)
                with lock:
                    used += existing
                self.size[url] = existing
                return
            try:
                data = lib.http_get(self.fetch[url], retries=3, timeout=180)
            except Exception as exc:  # noqa: BLE001
                self.skipped.append({"url": url, "reason": f"fetch failed: {exc}"})
                return
            if len(data) > cap_for(url):
                self.skipped.append({"url": url, "reason": f"too large ({lib.human_size(len(data))})"})
                return
            with lock:
                if self.budget_bytes and used + len(data) > self.budget_bytes:
                    self.skipped.append({"url": url, "reason": "超出总体积预算，未收录"})
                    return
                used += len(data)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
            self.size[url] = len(data)

        with ThreadPoolExecutor(max_workers=jobs) as ex:
            futures = {ex.submit(one, u): u for u in plan}
            for fut in as_completed(futures):
                fut.result()
                done += 1
                if done % 25 == 0 or done == len(plan):
                    lib.log(f"    {done}/{len(plan)} assets · {lib.human_size(used)}")

    def _remote_fallback(self, clean_url: str) -> str:
        return self.fetch.get(clean_url, clean_url)


# --------------------------------------------------------------------------- nav
def build_sidebar(trees: dict[int, list], section: str, current_id: int | None) -> str:
    parts = ['<aside><div class="sec">文档目录</div>']
    for dt, slug, label, _ in SECTIONS:
        nodes = trees.get(dt) or []
        if not nodes:
            continue
        active = ' style="color:#0b6bcb;font-weight:700"' if slug == section else ""
        parts.append(f'<div class="sec"{active}>{esc(label)}</div><ul>')
        flat = flatten(nodes, [])
        for doc in flat:
            trail = doc["trail"][:-1]
            cls = ""
            label_txt = esc(doc["name"])
            if trail:
                label_txt = f'<span style="color:#8b95a3">{esc(" / ".join(trail))} / </span>{label_txt}'
            on = " on" if doc["id"] == current_id else ""
            parts.append(f'<li><a class="{on.strip()}" href="../{slug}/{slug_for(slug, doc)}.html">{label_txt}</a></li>')
        parts.append("</ul>")
    parts.append("</aside>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- crawl
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--max-asset-mb", type=float, default=60.0)
    ap.add_argument("--max-video-mb", type=float, default=60.0)
    ap.add_argument("--budget-mb", type=float, default=650.0, help="总媒体体积预算")
    ap.add_argument("--max-docs", type=int, default=0, help="limit docs per section (debug)")
    ap.add_argument("--no-assets", action="store_true", help="skip downloading media/attachments")
    args = ap.parse_args()

    root = os.path.abspath(args.out)
    dry = args.no_assets
    mb = 1024 * 1024
    assets = Assets(
        root,
        int(args.max_asset_mb * mb),
        dry,
        max_video_bytes=int(args.max_video_mb * mb),
        budget_bytes=int(args.budget_mb * mb),
    )

    lib.log("1/5 fetching document trees …")
    trees: dict[int, list] = {}
    for dt, slug, label, _ in SECTIONS:
        nodes = lib.doc_tree(dt)
        trees[dt] = nodes
        lib.write_json(os.path.join(root, "raw", f"tree-{dt}-{slug}.json"), nodes)
        lib.log(f"   documentType={dt} ({label}): {len(flatten(nodes, []))} documents")

    plans: dict[int, list[dict]] = {}
    for dt, slug, _, _ in SECTIONS:
        docs = flatten(trees[dt], [])
        if args.max_docs:
            docs = docs[: args.max_docs]
        for d in docs:
            d["slug"] = slug_for(slug, d)
        plans[dt] = docs

    # id -> page so that #/document/index?id=NN can be rewritten to a local page
    id_page: dict[int, tuple[str, str]] = {}
    for dt, slug, _, _ in SECTIONS:
        for d in plans[dt]:
            id_page[d["id"]] = (slug, d["slug"])

    lib.log("2/5 fetching document bodies …")
    rendered: dict[tuple[str, str], dict] = {}
    flat_all = [(dt, slug, d) for dt, slug, _, _ in SECTIONS for d in plans[dt]]
    bodies: dict[int, str] = {}

    def fetch_body(item):
        dt, slug, d = item
        try:
            html = lib.doc_content(d["id"])
        except Exception as exc:  # noqa: BLE001
            lib.log(f"   !! doc {d['id']} {d['name']}: {exc}")
            html = ""
        return d["id"], html

    with ThreadPoolExecutor(max_workers=min(args.jobs, 6)) as ex:
        for i, (did, html) in enumerate(ex.map(fetch_body, flat_all), 1):
            bodies[did] = html
            if i % 20 == 0 or i == len(flat_all):
                lib.log(f"   {i}/{len(flat_all)} documents")

    lib.log("3/5 rewriting links and collecting media …")
    for dt, slug, d in flat_all:
        html = bodies.get(d["id"], "")
        lib.write_json(
            os.path.join(root, "raw", f"doc-{d['id']}.json"),
            {
                "id": d["id"],
                "documentType": dt,
                "breadcrumb": d["trail"],
                "sourceUrl": f"{BASE}/#/document/index?id={d['id']}" if dt != 3 else f"{BASE}/#/developTools/apiLibDetails?id={d['id']}",
                "html": html,
            },
        )
        if not html:
            continue
        tree = dom.parse(html)

        def resolver(raw: str) -> str | None:
            href = (raw or "").strip()
            if not href:
                return None
            m = re.search(r"#/document/index\?id=(\d+)", href)
            if m:
                target = id_page.get(int(m.group(1)))
                if target:
                    sec, docslug = target
                    prefix = "" if sec == slug else f"../{sec}/"
                    return f"{prefix}{docslug}.html"
                return href
            if href.startswith(("mailto:", "#")):
                return href
            rel = assets.register(href)
            if rel and rel.startswith(("assets/", "downloads/")):
                return "../" + rel
            return rel

        dom.rewrite_tree(tree, resolver)
        md = dom.to_markdown(tree, heading_offset=1)
        rendered[(slug, d["slug"])] = {
            "doc": d,
            "html": dom.render_html(tree),
            "markdown": md,
            "text": re.sub(r"\s+", " ", dom.text_of(tree)).strip(),
            "sourceUrl": (
                f"{BASE}/#/developTools/apiLibDetails?id={d['id']}"
                if dt == 3
                else f"{BASE}/#/document/index?id={d['id']}"
            ),
        }

    assets.fetch_all(args.jobs)

    lib.log("4/5 writing pages …")
    index_entries: list[dict] = []
    for dt, slug, label, blurb in SECTIONS:
        section_dir = os.path.join(root, slug)
        os.makedirs(section_dir, exist_ok=True)
        docs = plans[dt]
        cards = "".join(
            f'<a class="card" href="{d["slug"]}.html"><div class="t">{esc(d["name"])}</div>'
            f'<div class="d">{esc(" / ".join(d["trail"][:-1])) or esc(blurb)}</div></a>'
            for d in docs
        )
        body = (
            f'<div class="hero"><h1>{esc(label)}</h1><p>{esc(blurb)}</p>'
            f'<p class="meta">共 {len(docs)} 篇 · 采集自 openplatform.byd.com</p></div>'
            f'<div class="cards">{cards}</div>'
        )
        lib.write_text(
            os.path.join(section_dir, "index.html"),
            page(title=label, body=body, depth=1, active=slug, sidebar=build_sidebar(trees, slug, None)),
        )

    order = {slug: [(dt, d) for dt, s, d in flat_all if s == slug] for _, slug, _, _ in SECTIONS}
    for slug, docs in order.items():
        for i, (dt, d) in enumerate(docs):
            rec = rendered.get((slug, d["slug"]))
            if not rec:
                continue
            prev_doc = docs[i - 1][1] if i > 0 else None
            next_doc = docs[i + 1][1] if i + 1 < len(docs) else None
            pager = '<div class="pager">'
            pager += (
                f'<a href="{prev_doc["slug"]}.html">← {esc(prev_doc["name"])}</a>' if prev_doc else "<span></span>"
            )
            pager += (
                f'<a href="{next_doc["slug"]}.html">{esc(next_doc["name"])} →</a>' if next_doc else "<span></span>"
            )
            pager += "</div>"
            crumb = " / ".join(
                f'<a href="index.html">{esc(x)}</a>' for x in [dict(SECTIONS_BY_SLUG)[slug]] + d["trail"][:-1]
            )
            body = (
                f'<div class="crumb">{crumb}</div>'
                f'<h1>{esc(d["name"])}</h1>'
                f'<div class="meta">来源：{esc(" / ".join(d["trail"]))} · '
                f'文档 ID {d["id"]} · <a href="{esc(rec.get("sourceUrl", BASE))}" target="_blank" rel="noopener">原始页面</a></div>'
                f'<article>{rec["html"]}</article>{pager}'
            )
            lib.write_text(
                os.path.join(root, slug, f'{d["slug"]}.html'),
                page(title=d["name"], body=body, depth=1, active=slug, sidebar=build_sidebar(trees, slug, d["id"])),
            )
            md_path = os.path.join(root, "markdown", slug, f'{d["slug"]}.md')
            lib.write_text(
                md_path,
                f"# {d['name']}\n\n> 来源：{' / '.join(d['trail'])} · {BASE}/#/document/index?id={d['id']}\n\n"
                + rec["markdown"],
            )
            index_entries.append(
                {
                    "t": d["name"],
                    "c": " / ".join(d["trail"][:-1]),
                    "s": slug,
                    "u": f"{slug}/{d['slug']}.html",
                    "m": f"markdown/{slug}/{d['slug']}.md",
                    "x": rec["text"][:600],
                }
            )

    lib.write_json(os.path.join(root, "search.json"), index_entries)
    total_assets = sum(assets.size.values())
    lib.write_json(
        os.path.join(root, "manifest.json"),
        {
            "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": BASE,
            "sections": {slug: len(plans[dt]) for dt, slug, _, _ in SECTIONS},
            "assetCount": len(assets.map),
            "assetBytes": total_assets,
            "assets": [
                {
                    "url": u,
                    "path": p,
                    "size": assets.size.get(u, 0),
                    "originalName": assets.original.get(u, ""),
                }
                for u, p in sorted(assets.map.items())
                if u in assets.size
            ],
            "omitted": assets.skipped,
        },
    )
    lib.write_json(os.path.join(root, "omitted.json"), assets.skipped)
    lib.log(
        f"   pages: {len(index_entries)} · assets kept: {len(assets.size)} "
        f"({lib.human_size(total_assets)}) · omitted: {len(assets.skipped)}"
    )
    lib.log(f"   http ok={lib.STATS['http_ok']} fail={lib.STATS['http_fail']} bytes={lib.human_size(lib.STATS['bytes'])}")
    return 0


SECTIONS_BY_SLUG = {slug: label for _, slug, label, _ in SECTIONS}


if __name__ == "__main__":
    sys.exit(main())
