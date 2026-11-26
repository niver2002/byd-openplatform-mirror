#!/usr/bin/env python3
"""Build the hand-crafted sections of the mirror: home, contest hub, downloads,
search page, stylesheet and the single-file API reference."""

from __future__ import annotations

import datetime
import html as htmlmod
import json
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lib  # noqa: E402
from page import CSS, SITE_TITLE, esc, page  # noqa: E402

BASE = lib.BASE
HERE = os.path.dirname(os.path.abspath(__file__))

SECTIONS = [
    (1, "dev", "开发者文档", "开发者注册认证、开发套件、AIoT 业务、应用分发、主题商店、平台协议、规则中心等官方全量文档"),
    (2, "protocol", "协议规范", "软件开发协议（直连 / 云云对接 / OTA）与硬件接口规范（螺纹、椅背、中控生态接口）"),
    (3, "api", "API 库", "车机开放 API：车身、行驶数据、车速、能量模式、全景摄像头、空调、空气质量、门锁、车灯、雷达、充电、轮胎、仪表、传感器等 21 类接口"),
]

CONTEST_DOC_IDS = {
    57: "参赛规则",
    58: "获奖通知说明",
    59: "大赛权益说明",
    55: "大赛用户协议",
    56: "大赛隐私政策",
    62: "监护人知情同意书",
    61: "儿童隐私保护声明",
}


def load_json(path, default=None):
    return lib.read_json(path, default)


def contest_api_snapshot(root: str) -> dict:
    snap = {}
    endpoints = {
        "announcement": "/api/message-portal/announcement/list",
        "activities": "/api/document-portal/activity/listOnline",
        "advertisement_1": "/api/document-portal/document/portal/getAdvertisementByPosition?dropPosition=1",
        "contestSchedule_edition2": "/api/theme-portal/contest/getContestSchedule?contestEdition=2",
    }
    for key, path in endpoints.items():
        try:
            snap[key] = lib.api_get(path)
        except Exception as exc:  # noqa: BLE001
            snap[key] = {"_error": str(exc)}
    lib.write_json(os.path.join(root, "contest", "data", "api-snapshot.json"), snap)
    return snap


def build_contest(root: str, snap: dict, contest_data: dict) -> dict:
    outdir = os.path.join(root, "contest")
    os.makedirs(os.path.join(outdir, "data"), exist_ok=True)

    tracks = contest_data.get("tracks", {})
    resources = contest_data.get("resources", [])

    # captured browser render, when the playwright step ran
    captured_txt = ""
    cap_path = os.path.join(outdir, "captured", "theme-competation-index.txt")
    if os.path.exists(cap_path):
        captured_txt = open(cap_path, encoding="utf-8").read().strip()

    sched = (snap.get("contestSchedule_edition2") or {}).get("result")
    sched_html = ""
    if isinstance(sched, (list, dict)) and sched:
        sched_html = (
            '<h2 id="schedule">赛程安排</h2><div class="jsonview"><pre>'
            + esc(json.dumps(sched, ensure_ascii=False, indent=2))
            + "</pre></div>"
        )
    else:
        sched_html = (
            '<h2 id="schedule">赛程安排</h2>'
            '<div class="note">官方赛程接口 <code>/api/theme-portal/contest/getContestSchedule?contestEdition=2</code> '
            "返回 <code>登录令牌丢失</code>（需登录态），因此本镜像未包含赛程表。可在登录后访问 "
            f'<a href="{BASE}/#/theme-competation/index" target="_blank" rel="noopener">官方赛事页</a> 查看。</div>'
        )

    track_cards = []
    for key, t in tracks.items():
        reqs = "".join(f"<li>{esc(x)}</li>" for x in t.get("requirements", []))
        subs = "".join(f"<li>{esc(x)}</li>" for x in t.get("submissionSpec", []))
        track_cards.append(
            f'<section style="border:1px solid var(--line);border-radius:10px;padding:18px 22px;margin:16px 0">'
            f'<h3 id="{esc(key)}" style="margin-top:0">{esc(t.get("name", key))}</h3>'
            f'<p>{esc(t.get("description", ""))}</p>'
            f"<h4>作品要求</h4><ul>{reqs}</ul>"
            f"<h4>提交规范</h4><ul>{subs}</ul></section>"
        )

    announce = (snap.get("announcement") or {}).get("result") or []
    ann_html = "".join(
        f'<li><strong>{esc(a.get("name", ""))}</strong> — {esc(a.get("content", ""))}'
        f'<span class="tag">{esc(a.get("startTime", ""))} ~ {esc(a.get("endTime", ""))}</span></li>'
        for a in announce
    ) or "<li>（公告接口当前无内容）</li>"

    docs = load_json(os.path.join(root, "search.json"), []) or []
    doc_links = []
    for entry in docs:
        m = re.match(r"(\d+)-", entry["u"].split("/")[-1])
        if not m:
            continue
        did = int(m.group(1))
        if did in CONTEST_DOC_IDS:
            doc_links.append(
                f'<div class="dl"><div><div class="nm">{esc(entry["t"])}</div>'
                f'<div class="sub">{esc(entry["c"])}</div></div>'
                f'<a class="btn" href="../{esc(entry["u"])}">阅读</a></div>'
            )
        if did == 55:
            continue
    if not doc_links:
        doc_links.append(
            '<div class="note">赛事相关官方文档请见 <a href="../dev/index.html">开发者文档</a> 中的'
            "「主题商店业务 → 比亚迪智能座舱设计大赛」与「平台协议」章节。</div>"
        )

    res_rows = []
    missing = '<span class="tag">站点未提供下载地址</span>'
    for r in resources:
        cell = missing if not r.get("downloadUrl") else esc(r["downloadUrl"])
        res_rows.append(
            f"<tr><td>{esc(r.get('name', ''))}</td><td>{esc(r.get('type', ''))}</td>"
            f"<td>{esc(r.get('format', ''))}</td><td>{esc(r.get('size', ''))}</td>"
            f"<td>{cell}</td></tr>"
        )

    captured_html = ""
    shot = os.path.join(outdir, "captured", "theme-competation-index.png")
    shot_html = ""
    if os.path.exists(shot):
        shot_html = (
            '<h2 id="shot">官方赛事页整屏快照</h2>'
            '<p>下面是官方赛事首页在 1440px 宽浏览器中的渲染截图（已存入仓库，不依赖原站）。</p>'
            '<p><a href="captured/theme-competation-index.png" target="_blank" rel="noopener">'
            '<img src="captured/theme-competation-index.png" alt="2026 比亚迪智能座舱设计大赛官方页面截图"></a></p>'
        )
    if captured_txt:
        captured_html = (
            '<h2 id="captured">官方赛事页正文快照</h2>'
            '<div class="note">以下为无头浏览器渲染 <code>/#/theme-competation/index</code> 后提取的可见文本，'
            f'完整 HTML 见 <a href="captured/theme-competation-index.html">captured/theme-competation-index.html</a>。</div>'
            f'<pre style="white-space:pre-wrap;background:var(--code);padding:14px;border-radius:8px;font-size:13.5px;line-height:1.9">{esc(captured_txt)}</pre>'
        )
    packs = ""
    pack_manifest = load_json(os.path.join(outdir, "pack", "manifest.json"))
    if pack_manifest:
        packs = f"""
<h2 id="pack">官方赛事资料包</h2>
<p>比亚迪官方放出的《{esc(pack_manifest['fileName'])}》（原始压缩包 {lib.human_size(pack_manifest['zipBytes'])}）
已完整解包入库，共 {pack_manifest['fileCount']} 个文件、{lib.human_size(pack_manifest['totalBytes'])}：
内外饰车体图、座舱空间示意、LOGO 四联标、大赛设计说明、品牌字体、设计模板 `.pix`。</p>
<p><a class="btn" href="pack/index.html">浏览 / 下载资料包</a></p>
"""

    body = f"""
<div class="hero">
  <h1>2026 比亚迪智能座舱设计大赛</h1>
  <p>比亚迪生态开放平台主题共创赛事 · 赛道资料、参赛规则、权益说明与官方资料包镜像。</p>
  <p class="meta">数据来源：<a href="{BASE}/#/theme-competation/index" target="_blank" rel="noopener">openplatform.byd.com/#/theme-competation/index</a>
  · 采集时间 {esc(datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}</p>
</div>

{shot_html}

{packs}

<h2 id="announcement">赛事公告</h2>
<ul>{ann_html}</ul>

<h2 id="tracks">赛道设置</h2>
<p>大赛共设三个赛道：<strong>座舱交互前瞻赛道</strong>、<strong>座舱主题赛道</strong>、<strong>亲子壁纸赛道</strong>。
以下赛道详情取自官方前端数据模块。</p>
{''.join(track_cards)}

{sched_html}

<h2 id="docs">官方赛事文档</h2>
<p>以下文档来自开放平台文档中心（documentType=1），为大赛的规则与法律文本。</p>
{''.join(doc_links)}

<h2 id="resources">赛事资料下载（官方资源清单）</h2>
<div class="note">{esc(contest_data.get('_resource_note', ''))}</div>
<table><thead><tr><th>资源名称</th><th>类型</th><th>格式</th><th>大小</th><th>下载地址</th></tr></thead>
<tbody>{''.join(res_rows)}</tbody></table>
<p>官方实际可下载的设计规范与模板已收录在 <a href="../downloads/index.html">资料包下载页</a>。</p>

{captured_html}

<h2 id="files">本次赛事相关的可下载文件</h2>
<ul>
  <li><a href="../downloads/index.html">全部资料包列表</a>（含主题商店设计模板 sketch / pix、主题审核资料明细、车身开放 API JAR 包等）</li>
  <li><a href="data/api-snapshot.json">赛事接口原始响应 JSON</a></li>
  <li><a href="../markdown/contest/tracks.md">赛道详情 Markdown</a></li>
</ul>
"""
    lib.write_text(
        os.path.join(outdir, "index.html"),
        page(title="2026 比亚迪智能座舱设计大赛", body=body, depth=1, active="contest",
             sidebar=contest_sidebar()),
    )

    # markdown mirror of the contest hub
    md = ["# 2026 比亚迪智能座舱设计大赛", "", f"> 来源：{BASE}/#/theme-competation/index", ""]
    md.append("## 赛事公告")
    for a in announce:
        md.append(f"- **{a.get('name','')}** — {a.get('content','')} （{a.get('startTime','')} ~ {a.get('endTime','')}）")
    md.append("")
    md.append("## 赛道设置")
    for key, t in tracks.items():
        md.append(f"### {t.get('name', key)}")
        md.append("")
        md.append(t.get("description", ""))
        md.append("")
        md.append("**作品要求**")
        for x in t.get("requirements", []):
            md.append(f"- {x}")
        md.append("")
        md.append("**提交规范**")
        for x in t.get("submissionSpec", []):
            md.append(f"- {x}")
        md.append("")
    md.append("## 赛事资料清单（官方资源）")
    md.append("")
    md.append(f"> {contest_data.get('_resource_note','')}")
    md.append("")
    md.append("| 资源 | 类型 | 格式 | 大小 |")
    md.append("|---|---|---|---|")
    for r in resources:
        md.append(f"| {r.get('name','')} | {r.get('type','')} | {r.get('format','')} | {r.get('size','')} |")
    lib.write_text(os.path.join(root, "markdown", "contest", "tracks.md"), "\n".join(md).strip() + "\n")
    return {"tracks": len(tracks), "resources": len(resources)}


def contest_sidebar() -> str:
    links = [
        ("#pack", "官方资料包"),
        ("#shot", "官方页面快照"),
        ("#announcement", "赛事公告"),
        ("#tracks", "赛道设置"),
        ("#schedule", "赛程安排"),
        ("#docs", "官方赛事文档"),
        ("#resources", "赛事资料清单"),
        ("#captured", "官方页面对照"),
        ("#files", "可下载文件"),
        ("../downloads/index.html", "其它资料包"),
    ]
    items = "".join(f'<li><a href="{h}">{esc(t)}</a></li>' for h, t in links)
    return f'<aside><div class="sec">赛事目录</div><ul>{items}</ul></aside>'


def build_downloads(root: str) -> list[dict]:
    manifest = load_json(os.path.join(root, "manifest.json"), {}) or {}
    assets = manifest.get("assets", [])
    rows = []
    items = []
    for a in assets:
        path = a.get("path", "")
        if not path.startswith("downloads/"):
            continue
        dest = os.path.join(root, path)
        if not os.path.exists(dest):
            continue
        size = os.path.getsize(dest)
        name = a.get("originalName") or os.path.basename(path)
        items.append({"name": name, "path": path, "size": size, "url": a.get("url", "")})
    items.sort(key=lambda x: (-x["size"], x["name"]))
    for it in items:
        rows.append(
            f'<div class="dl"><div><div class="nm">{esc(it["name"])}</div>'
            f'<div class="sub">{lib.human_size(it["size"])} · 原始来源 <a href="{esc(it["url"])}" target="_blank" rel="noopener">链接</a></div>'
            f'</div><a class="btn" href="../{esc(it["path"])}" download>下载</a></div>'
        )

    omitted = load_json(os.path.join(root, "omitted.json"), []) or []
    omitted_html = ""
    if omitted:
        lis = "".join(
            f'<li>{esc(os.path.basename(urllib.parse.urlparse(o.get("url", "")).path))}'
            f' · {lib.human_size(o.get("size") or 0)} · {esc(o.get("reason", ""))}'
            f' · <a href="{esc(o.get("localFallback") or o.get("url", ""))}" target="_blank" rel="noopener">原站链接</a></li>'
            for o in omitted[:200]
        )
        omitted_html = (
            f"<h2>未收录的大体积文件（{len(omitted)}）</h2>"
            '<div class="note">以下文件超过体积预算，未镜像到仓库。链接指向原站（CDN 签名会过期，过期后需到原站对应文档页查看）。'
            "如需全量收录，重跑 <code>scripts/refresh.ps1 -MaxAssetMb 200 -BudgetMb 2000</code> 即可。</div>"
            f"<ul>{lis}</ul>"
        )
    body = f"""
<div class="hero"><h1>资料包下载</h1>
<p>从开放平台各文档中提取出的全部可下载附件（设计模板、规范表格、API SDK、测试报告模板等），已完整保存到本站，可直接下载，不依赖原站链接。</p></div>
<div class="note">原站附件地址带有时效签名，本站已把文件本体镜像到仓库内，因此长期可用。</div>
{''.join(rows) or '<div class="note">未发现可下载附件。</div>'}
{omitted_html}
<h2>整站打包</h2>
<p>所有文档、图片、附件与原始 JSON 都在本仓库中，可在 GitHub 页面使用 <strong>Code → Download ZIP</strong> 一次性下载整站，
或 <code>git clone</code> 本仓库。纯文本内容也提供了 Markdown 版本：<a href="../markdown/index.html">markdown/</a>。</p>
"""
    lib.write_text(
        os.path.join(root, "downloads", "index.html"),
        page(title="资料包下载", body=body, depth=1, active="downloads", sidebar=files_sidebar(items)),
    )
    return items


def files_sidebar(items: list[dict]) -> str:
    links = "".join(
        f'<li><a href="../{esc(i["path"])}">{esc(i["name"])}</a></li>' for i in items[:40]
    )
    return f'<aside><div class="sec">文件列表</div><ul>{links}</ul></aside>'


def build_home(root: str, stats: dict, downloads: list[dict]) -> None:
    search = load_json(os.path.join(root, "search.json"), []) or []
    total_dl = sum(i["size"] for i in downloads)
    cards = [
        ("contest/index.html", "2026 智能座舱设计大赛", "赛道资料、参赛规则、权益说明、页面对照快照", "赛事专区"),
        ("api/index.html", "API 库", "车机开放 API 全量接口定义（21 类），含方法、参数、键值与示例", f"{stats.get('api', 0)} 篇"),
        ("dev/index.html", "开发者文档", "注册认证、AIoT、应用分发、主题商店、协议与规则中心", f"{stats.get('dev', 0)} 篇"),
        ("protocol/index.html", "协议规范", "直连接入 / 云云对接 / OTA 升级 / 生态硬件接口规范", f"{stats.get('protocol', 0)} 篇"),
        ("downloads/index.html", "资料包下载", "设计模板、规范表格、API JAR 包等全部附件（已存入仓库）", f"{len(downloads)} 个文件"),
        ("search.html", "全文搜索", "在全部镜像文档中检索标题与正文", f"{len(search)} 条"),
    ]
    card_html = "".join(
        f'<a class="card" href="{u}"><div class="t">{esc(t)}</div><div class="d">{esc(d)}</div>'
        f'<div class="n">{esc(n)}</div></a>'
        for u, t, d, n in cards
    )
    body = f"""
<div class="hero">
  <h1>比亚迪生态开放平台 · 资料镜像</h1>
  <p>把 <a href="{BASE}/" target="_blank" rel="noopener">openplatform.byd.com</a> 上的赛事资料、赛事资料包与完整开放 API 文档
  完整抓取并本地化为可离线浏览的静态站点。所有正文、图片、视频与附件都已存入本仓库，不依赖原站（原站图片链接带时效签名，过期即失效）。</p>
  <p class="meta">共 {len(search)} 篇文档 · {stats.get('assets', 0)} 个镜像资源 · 附件 {len(downloads)} 个（{lib.human_size(total_dl)}）</p>
</div>
<div class="cards">{card_html}</div>

<h2>怎么用</h2>
<ul>
  <li><strong>看赛事</strong>：<a href="contest/index.html">赛事专区</a> → 赛道要求、参赛规则、权益说明、资料清单。</li>
  <li><strong>写代码</strong>：<a href="api/index.html">API 库</a> 是车机端 Java 开放接口的完整参考；单文件版本见
      <a href="api/all.html">全部 API 合集</a> 或 <a href="markdown/byd-api-reference.md">Markdown 合集</a>。</li>
  <li><strong>要文件</strong>：<a href="downloads/index.html">资料包下载</a>，包含设计模板 <code>.sketch/.pix</code>、
      审核资料明细 <code>.xlsx</code>、车身开放 API <code>bydauto-openapi.jar</code> 等。</li>
  <li><strong>离线读</strong>：<code>git clone</code> 本仓库即可，<a href="markdown/">markdown/</a> 目录有全部文档的 Markdown 版。</li>
</ul>

<h2>数据与许可</h2>
<div class="note">
本站内容版权归<strong>比亚迪汽车工业有限公司</strong>所有，仅为参赛者与开发者离线查阅、检索便利而做技术性归档，未作任何修改或商业使用。
如权利人认为不妥，请提交 issue，将立即删除。原始站点：<a href="{BASE}/" target="_blank" rel="noopener">openplatform.byd.com</a>。
</div>

<h2>内容清单</h2>
<ul>
  <li>开发者文档 {stats.get('dev', 0)} 篇（documentType=1）</li>
  <li>协议规范 {stats.get('protocol', 0)} 篇（documentType=2）</li>
  <li>API 库 {stats.get('api', 0)} 篇（documentType=3）</li>
  <li>赛事接口原始响应：<a href="contest/data/api-snapshot.json">api-snapshot.json</a></li>
  <li>整站清单：<a href="manifest.json">manifest.json</a>（每个资源的原始 URL 与本地路径）</li>
</ul>
"""
    lib.write_text(
        os.path.join(root, "index.html"),
        page(title="首页", body=body, depth=0, active="", sidebar=""),
    )


def build_search(root: str) -> None:
    body = """
<div class="hero"><h1>全文搜索</h1><p>在全部镜像文档中检索标题与正文。</p></div>
<input id="q" type="search" placeholder="输入关键字，例如：空调、getAutoVIN、主题、监护人…" autofocus>
<p id="st" class="meta" style="margin-top:10px">共 0 条</p>
<div id="hits"></div>
<script>
let DATA = [];
fetch('search.json').then(r=>r.json()).then(d=>{DATA=d;document.getElementById('st').textContent='共 '+d.length+' 条文档，输入关键字开始检索';});
const q = document.getElementById('q');
const hits = document.getElementById('hits');
const st = document.getElementById('st');
function run(){
  const kw = q.value.trim().toLowerCase();
  if(!kw){ hits.innerHTML=''; st.textContent='共 '+DATA.length+' 条文档，输入关键字开始检索'; return; }
  const parts = kw.split(/\\s+/).filter(Boolean);
  const res = DATA.filter(d=>{
    const hay = (d.t+' '+d.c+' '+(d.x||'')).toLowerCase();
    return parts.every(p=>hay.includes(p));
  }).slice(0,200);
  st.textContent = '匹配 '+res.length+' 条';
  hits.innerHTML = res.map(d=>{
    const hay=(d.x||''); let i=hay.toLowerCase().indexOf(parts[0]); if(i<0)i=0;
    const snip = (i>40?'…':'')+hay.slice(Math.max(0,i-40), Math.max(0,i-40)+160)+(hay.length>i+200?'…':'');
    return `<div class="hit"><div class="h"><a href="${d.u}">${d.t}</a> <span class="tag">${d.c||d.s}</span></div>
      <div class="s">${snip}</div></div>`;
  }).join('') || '<div class="note">没有匹配结果。</div>';
}
q.addEventListener('input', run);
</script>
"""
    lib.write_text(
        os.path.join(root, "search.html"),
        page(title="搜索", body=body, depth=0, active="search.html", sidebar=""),
    )


def build_api_reference(root: str) -> None:
    """One page + one markdown file containing the complete API library."""
    api_dir = os.path.join(root, "api")
    search = load_json(os.path.join(root, "search.json"), []) or []
    api_docs = [e for e in search if e["s"] == "api"]
    api_docs.sort(key=lambda e: int(e["u"].split("/")[-1].split("-")[0]))

    parts_html = []
    parts_md = ["# 比亚迪车机开放 API 全量参考", "",
                f"> 采集自 {BASE}/#/developTools/apiLib · 共 {len(api_docs)} 篇", ""]
    toc = []
    for e in api_docs:
        rel = e["u"].split("/")[-1]
        page_path = os.path.join(api_dir, rel)
        if not os.path.exists(page_path):
            continue
        src = open(page_path, encoding="utf-8").read()
        m = re.search(r"<article>(.*?)</article>", src, re.S)
        inner = m.group(1) if m else ""
        anchor = rel[:-5]
        toc.append(f'<li><a href="#{esc(anchor)}">{esc(e["t"])}</a></li>')
        parts_html.append(
            f'<section id="{esc(anchor)}" style="margin:36px 0 0"><div style="font-size:12px;color:#5c6572">'
            f'<a href="{esc(rel)}">独立页面</a></div>{inner}</section>'
        )
        md_path = os.path.join(root, "markdown", "api", rel[:-5] + ".md")
        if os.path.exists(md_path):
            parts_md.append(open(md_path, encoding="utf-8").read().strip())
            parts_md.append("\n\n---\n")

    body = f"""<div class="hero"><h1>API 库 · 全量合集</h1>
<p>把开放平台 API 库的全部 {len(api_docs)} 篇文档合并为一页，便于 Ctrl+F 与批量检索。</p></div>
<ul>{''.join(toc)}</ul>
{''.join(parts_html)}
"""
    lib.write_text(
        os.path.join(root, "api", "all.html"),
        page(title="API 库全量合集", body=body, depth=1, active="api", sidebar=api_sidebar(api_docs)),
    )
    lib.write_text(os.path.join(root, "markdown", "byd-api-reference.md"), "\n".join(parts_md))


def api_sidebar(api_docs: list[dict]) -> str:
    items = "".join(f'<li><a href="#{esc(d["u"].split("/")[-1][:-5])}">{esc(d["t"])}</a></li>' for d in api_docs)
    return f'<aside><div class="sec">API 分类</div><ul>{items}</ul></aside>'


def build_markdown_index(root: str) -> None:
    search = load_json(os.path.join(root, "search.json"), []) or []
    groups: dict[str, list[dict]] = {}
    for e in search:
        groups.setdefault(e["s"], []).append(e)
    names = {"api": "API 库", "dev": "开发者文档", "protocol": "协议规范"}
    blocks = []
    for sec, items in groups.items():
        lis = "".join(
            f'<li><a href="../{esc(i["m"])}">{esc(i["t"])}</a> <span class="tag">{esc(i["c"])}</span></li>'
            for i in items
        )
        blocks.append(f"<h2>{esc(names.get(sec, sec))}（{len(items)}）</h2><ul>{lis}</ul>")
    body = (
        '<div class="hero"><h1>Markdown 镜像</h1>'
        "<p>全部文档的 Markdown 版本，适合放到本地笔记、知识库或做 RAG 检索语料。</p></div>" + "".join(blocks)
    )
    lib.write_text(
        os.path.join(root, "markdown", "index.html"),
        page(title="Markdown 镜像", body=body, depth=1, active="", sidebar=""),
    )


def main() -> int:
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "docs")
    os.makedirs(root, exist_ok=True)
    lib.write_text(os.path.join(root, "style.css"), CSS)
    lib.write_text(os.path.join(root, ".nojekyll"), "")

    contest_data = json.load(open(os.path.join(HERE, "contest_data.json"), encoding="utf-8"))
    lib.log("extras: snapshotting contest endpoints …")
    snap = contest_api_snapshot(root)
    stats = build_contest(root, snap, contest_data)

    lib.log("extras: downloads page …")
    items = build_downloads(root)

    manifest = load_json(os.path.join(root, "manifest.json"), {}) or {}
    sections = manifest.get("sections", {})
    counts = {
        "dev": sections.get("dev", 0),
        "protocol": sections.get("protocol", 0),
        "api": sections.get("api", 0),
        "assets": len(manifest.get("assets", [])),
    }
    lib.log("extras: home / search / api reference / markdown index …")
    build_home(root, counts, items)
    build_search(root)
    build_api_reference(root)
    build_markdown_index(root)
    lib.write_json(os.path.join(root, "contest", "data", "tracks.json"), contest_data)
    lib.log(f"extras: done · tracks={stats['tracks']} resources={stats['resources']} downloads={len(items)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
