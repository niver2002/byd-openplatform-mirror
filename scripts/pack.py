#!/usr/bin/env python3
"""Mirror the official competition resource pack
(2026比亚迪智能座舱设计大赛资料.zip).

The archive is 253 MB and holds a single 82 MB file at most, so it is unpacked
into browsable, individually downloadable files instead of being committed as
one blob. The original zip is published as a GitHub release asset.

    python scripts/pack.py extract --zip C:/byd/pack.zip --out docs/contest/pack
    python scripts/pack.py index   --out docs/contest/pack
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lib  # noqa: E402
from page import esc, page  # noqa: E402

PACK_URL = (
    "https://openplatform.byd.com/"
    "2026%E6%AF%94%E4%BA%9A%E8%BF%AA%E6%99%BA%E8%83%BD%E5%BA%A7%E8%88%B1%E8%AE%BE%E8%AE%A1%E5%A4%A7%E8%B5%9B%E8%B5%84%E6%96%99.zip"
)
PACK_NAME = "2026比亚迪智能座舱设计大赛资料.zip"
# The 253 MB archive exceeds git's 100 MB per-file limit, so it is published as
# a release asset and linked from the browsable mirror.
RELEASE_TAG = "contest-pack-2026"
RELEASE_ASSET = "byd-2026-cockpit-design-contest-pack.zip"
RELEASE_URL = (
    "https://github.com/niver2002/byd-openplatform-mirror/releases/download/"
    f"{RELEASE_TAG}/{RELEASE_ASSET}"
)

SKIP_PARTS = {"__MACOSX", ".DS_Store", "Thumbs.db", "desktop.ini"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}


def real_name(info: zipfile.ZipInfo) -> str:
    """Zip entries without the UTF-8 flag were stored as cp437-mangled UTF-8."""
    name = info.filename
    if info.flag_bits & 0x800:
        return name
    try:
        return name.encode("cp437").decode("utf-8")
    except Exception:  # noqa: BLE001
        try:
            return name.encode("cp437").decode("gbk")
        except Exception:  # noqa: BLE001
            return name


def safe_rel(name: str) -> str | None:
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p in SKIP_PARTS for p in parts):
        return None
    if any(p == ".." for p in parts):
        return None
    return "/".join(parts)


def cmd_extract(args) -> int:
    out = os.path.abspath(args.out)
    if os.path.isdir(out) and args.clean:
        shutil.rmtree(out)
    os.makedirs(out, exist_ok=True)

    zip_path = args.zip
    if not zip_path:
        zip_path = os.path.join(os.path.dirname(out), ".contest-pack.zip")
        if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 200 * 1024 * 1024:
            lib.log(f"pack: downloading {lib.human_size(0) or ''}{PACK_NAME} …")
            data = lib.http_get(PACK_URL, retries=3, timeout=900)
            with open(zip_path, "wb") as fh:
                fh.write(data)
        lib.log(f"pack: archive {lib.human_size(os.path.getsize(zip_path))}")

    digest = hashlib.sha256()
    with open(zip_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)

    rows = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel = safe_rel(real_name(info))
            if not rel:
                continue
            dest = os.path.join(out, *rel.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            rows.append({"path": rel, "size": os.path.getsize(dest)})

    manifest = {
        "source": PACK_URL,
        "fileName": PACK_NAME,
        "zipBytes": os.path.getsize(zip_path),
        "zipSha256": digest.hexdigest(),
        "extractedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "fileCount": len(rows),
        "totalBytes": sum(r["size"] for r in rows),
        "files": sorted(rows, key=lambda r: r["path"]),
    }
    lib.write_json(os.path.join(out, "manifest.json"), manifest)
    lib.log(
        f"pack: extracted {len(rows)} files, {lib.human_size(manifest['totalBytes'])} "
        f"(zip {lib.human_size(manifest['zipBytes'])}, sha256 {manifest['zipSha256'][:16]}…)"
    )
    return 0


def _thumb_name(rel: str) -> str:
    return rel.replace("/", "__").rsplit(".", 1)[0] + ".jpg"


def cmd_index(args) -> int:
    out = os.path.abspath(args.out)
    manifest = lib.read_json(os.path.join(out, "manifest.json"))
    if not manifest:
        lib.log("pack: no manifest, run extract first")
        return 1

    thumbs_dir = os.path.join(out, "_thumbs")
    have_thumbs = {f for f in os.listdir(thumbs_dir)} if os.path.isdir(thumbs_dir) else set()

    groups: dict[str, list[dict]] = {}
    for row in manifest["files"]:
        top = row["path"].split("/")[0] if "/" in row["path"] else "（根目录）"
        groups.setdefault(top, []).append(row)

    sections = []
    for top in sorted(groups):
        rows = sorted(groups[top], key=lambda r: r["path"])
        cards, listrows = [], []
        for row in rows:
            rel = row["path"]
            ext = os.path.splitext(rel)[1].lower()
            label = rel.split("/", 1)[1] if "/" in rel else rel
            size = lib.human_size(row["size"])
            thumb = _thumb_name(rel)
            if ext in IMAGE_EXT and thumb in have_thumbs:
                cards.append(
                    f'<a class="pcard" href="{esc(rel)}" target="_blank" rel="noopener">'
                    f'<img src="_thumbs/{esc(thumb)}" alt="{esc(label)}" loading="lazy">'
                    f'<div class="pn">{esc(label)}</div><div class="ps">{size}</div></a>'
                )
            else:
                kind = "字体" if ext in FONT_EXT else (ext.lstrip(".").upper() or "文件")
                listrows.append(
                    f'<div class="dl"><div><div class="nm">{esc(label)}</div>'
                    f'<div class="sub">{esc(kind)} · {size}</div></div>'
                    f'<a class="btn" href="{esc(rel)}" download>下载</a></div>'
                )
        body = ""
        if cards:
            body += f'<div class="pgrid">{"".join(cards)}</div>'
        if listrows:
            body += "".join(listrows)
        sections.append(f"<h2>{esc(top)}（{len(rows)}）</h2>{body}")

    body = f"""
<div class="hero"><h1>官方赛事资料包</h1>
<p>比亚迪官方发布的《{esc(manifest['fileName'])}》已完整解包入库：{manifest['fileCount']} 个文件、
{lib.human_size(manifest['totalBytes'])}，可在下方逐个下载，或直接取原始压缩包。</p>
<p class="meta">原始包 {lib.human_size(manifest['zipBytes'])} · SHA-256 <code>{escm(manifest['zipSha256'])}</code></p></div>

<div class="note">整包下载（GitHub Release 附件，官方原文件 {lib.human_size(manifest['zipBytes'])}）：
<a href="{esc(RELEASE_URL)}" target="_blank" rel="noopener">{esc(manifest['fileName'])}</a>
&nbsp;·&nbsp;原始地址 <a href="{esc(manifest['source'])}" target="_blank" rel="noopener">openplatform.byd.com</a>
&nbsp;·&nbsp;下方每个文件都已单独入库，可免解压直接取用。</div>

{''.join(sections)}
"""
    lib.write_text(
        os.path.join(out, "index.html"),
        page(title="官方赛事资料包", body=body, depth=2, active="contest", sidebar=sidebar(groups)),
    )
    lib.log(f"pack: index written, groups={len(groups)}")
    return 0


def escm(text: str) -> str:
    return f'<span style="word-break:break-all">{esc(text)}</span>'


def sidebar(groups: dict) -> str:
    items = "".join(f'<li><a href="#{esc(t)}">{esc(t)}（{len(v)}）</a></li>' for t, v in sorted(groups.items()))
    return (
        '<aside><div class="sec">资料包目录</div><ul>' + items + "</ul>"
        '<div class="sec">相关</div><ul>'
        '<li><a href="../index.html">赛事专区</a></li>'
        '<li><a href="../../downloads/index.html">其它资料包</a></li></ul></aside>'
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--zip", default=None, help="local archive; downloaded from PACK_URL when omitted")
    e.add_argument("--out", required=True)
    e.add_argument("--clean", action="store_true")
    e.set_defaults(func=cmd_extract)
    i = sub.add_parser("index")
    i.add_argument("--out", required=True)
    i.set_defaults(func=cmd_index)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
