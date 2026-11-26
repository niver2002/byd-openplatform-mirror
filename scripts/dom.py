"""Tiny HTML tree builder with sanitising, asset-rewriting and markdown rendering.

The BYD document portal returns rich-text HTML with heavy inline styling.
We parse it into a small tree, strip anything unsafe, rewrite every asset URL
to a mirrored local path, then render two artefacts: a styled HTML page body
and a Markdown mirror.
"""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser

VOID = {"br", "img", "hr", "col", "meta", "link", "input", "source", "wbr"}

ALLOWED = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "strong", "b", "em", "i",
    "u", "s", "del", "ins", "sub", "sup", "ul", "ol", "li", "table", "thead",
    "tbody", "tfoot", "tr", "th", "td", "colgroup", "col", "blockquote", "pre",
    "code", "a", "img", "video", "source", "span", "div", "section", "figure",
    "figcaption", "dl", "dt", "dd",
}

DROP_WITH_CONTENT = {"script", "style", "noscript", "iframe", "object", "embed", "form", "input", "button", "svg", "canvas"}

ALLOWED_ATTRS = {
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "video": {"src", "poster", "controls", "width", "height", "preload"},
    "source": {"src", "type"},
    "td": {"colspan", "rowspan", "width"},
    "th": {"colspan", "rowspan", "width", "scope"},
    "col": {"width", "span"},
    "div": {"class"},
    "span": {"class"},
}


class Node:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag: str | None, attrs=None, text: str = ""):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: list[Node] = []
        self.text = text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Node {self.tag} {self.attrs} {len(self.children)}>"


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            # add a placeholder so handle_endtag can pop safely
            node = Node("#drop")
            self.stack[-1].children.append(node)
            self.stack.append(node)
            return
        if tag not in ALLOWED:
            return
        node = Node(tag, {k.lower(): (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in ALLOWED:
            self.stack[-1].children.append(
                Node(tag, {k.lower(): (v or "") for k, v in attrs})
            )

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            for i in range(len(self.stack) - 1, 0, -1):
                if self.stack[i].tag == "#drop":
                    del self.stack[i:]
                    return
            return
        if tag not in ALLOWED:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data:
            self.stack[-1].children.append(Node(None, text=data))


def parse(html: str) -> Node:
    b = _Builder()
    b.feed(html or "")
    b.close()
    return b.root


# ---------------------------------------------------------------- rewriting

def rewrite_tree(root: Node, resolver) -> None:
    """Walk the tree, drop unsafe attributes and ask `resolver` for new URLs."""
    for child in root.children:
        if child.tag is None:
            continue
        allowed = ALLOWED_ATTRS.get(child.tag, set())
        new_attrs = {}
        for key, value in child.attrs.items():
            if key in allowed:
                new_attrs[key] = value
        if child.tag == "a":
            href = new_attrs.get("href", "")
            if href.startswith(("javascript:", "data:")):
                new_attrs.pop("href", None)
            else:
                replaced = resolver(href)
                if replaced:
                    new_attrs["href"] = replaced
                else:
                    new_attrs.pop("href", None)
            new_attrs["rel"] = "noopener noreferrer"
            if new_attrs.get("href", "").startswith("http"):
                new_attrs["target"] = "_blank"
        elif child.tag in ("img", "video", "source"):
            for key in ("src", "poster"):
                if key in new_attrs:
                    replaced = resolver(new_attrs[key])
                    if replaced:
                        new_attrs[key] = replaced
                    else:
                        new_attrs.pop(key, None)
            if child.tag == "video":
                new_attrs["controls"] = "controls"
                new_attrs["preload"] = "metadata"
        elif child.tag == "td" or child.tag == "th":
            for key in ("colspan", "rowspan"):
                if key in new_attrs and not new_attrs[key].isdigit():
                    new_attrs.pop(key, None)
        child.attrs = new_attrs
        rewrite_tree(child, resolver)


def text_of(node: Node) -> str:
    if node.tag is None:
        return node.text
    if node.tag == "#drop":
        return ""
    return "".join(text_of(c) for c in node.children)


# ---------------------------------------------------------------- html render

def render_html(node: Node) -> str:
    if node.tag is None:
        return escape(node.text, quote=False)
    if node.tag in ("#root", "#drop"):
        return "".join(render_html(c) for c in node.children)
    attrs = "".join(
        f' {k}="{escape(str(v), quote=True)}"' for k, v in node.attrs.items() if v != ""
    )
    if node.tag in VOID:
        return f"<{node.tag}{attrs}>"
    inner = "".join(render_html(c) for c in node.children)
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


# ---------------------------------------------------------------- markdown

INLINE_WRAP = {"strong": "**", "b": "**", "em": "*", "i": "*", "code": "`", "del": "~~", "s": "~~"}

#: when embedding a document under our own H1, demote its headings by one level
_HEADING_OFFSET = 0


def _md_inline(node: Node) -> str:
    if node.tag is None:
        return node.text.replace("\n", " ")
    if node.tag == "#drop":
        return ""
    if node.tag == "br":
        return "  \n"
    if node.tag == "img":
        src = node.attrs.get("src", "")
        alt = node.attrs.get("alt", "")
        return f"![{alt}]({src})"
    if node.tag == "a":
        href = node.attrs.get("href", "")
        label = "".join(_md_inline(c) for c in node.children).strip() or href
        return f"[{label}]({href})" if href else label
    if node.tag == "video":
        src = node.attrs.get("src", "")
        return f"\n\n<video src=\"{src}\" controls></video>\n\n"
    if node.tag in INLINE_WRAP:
        inner = "".join(_md_inline(c) for c in node.children)
        mark = INLINE_WRAP[node.tag]
        return f"{mark}{inner}{mark}" if inner.strip() else inner
    inner = "".join(_md_inline(c) for c in node.children)
    return inner


def _md_block(node: Node, depth: int = 0) -> str:
    if node.tag is None:
        t = node.text.strip()
        return t + "\n\n" if t else ""
    if node.tag == "#drop":
        return ""
    tag = node.tag
    if tag == "#root":
        return "".join(_md_block(c, depth) for c in node.children)
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = min(6, int(tag[1]) + _HEADING_OFFSET)
        inner = "".join(_md_inline(c) for c in node.children).strip()
        return f"{'#' * level} {inner}\n\n" if inner else ""
    if tag == "p":
        inner = "".join(_md_inline(c) for c in node.children).strip()
        return f"{inner}\n\n" if inner else ""
    if tag in ("ul", "ol"):
        out = []
        idx = 1
        for child in node.children:
            if child.tag != "li":
                continue
            body = "".join(_md_block(c, depth + 1) for c in child.children).strip()
            body = body.replace("\n", "\n" + "  " * (depth + 1)).strip()
            bullet = f"{idx}." if tag == "ol" else "-"
            out.append("  " * depth + f"{bullet} {body}\n")
            idx += 1
        return "".join(out) + "\n"
    if tag == "blockquote":
        body = "".join(_md_block(c, depth) for c in node.children).strip()
        return "\n".join("> " + line for line in body.splitlines()) + "\n\n"
    if tag == "pre":
        return "```\n" + text_of(node).strip("\n") + "\n```\n\n"
    if tag == "table":
        return _md_table(node)
    if tag == "hr":
        return "---\n\n"
    inner = "".join(_md_block(c, depth) for c in node.children)
    return inner


def _md_table(node: Node) -> str:
    rows: list[list[str]] = []
    header_rows = 0
    for section in node.children:
        if section.tag == "tr":
            trs = [section]
        elif section.tag in ("thead", "tbody", "tfoot"):
            trs = [c for c in section.children if c.tag == "tr"]
            if section.tag == "thead":
                header_rows += len(trs)
        else:
            continue
        for tr in trs:
            cells = [c for c in tr.children if c.tag in ("td", "th")]
            row = []
            for cell in cells:
                txt = "".join(_md_block(c, 0) for c in cell.children).strip()
                txt = " ".join(txt.split())
                row.append(txt.replace("|", "\\|"))
            if row:
                rows.append(row)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head_at = 0 if header_rows else 0
    head = rows[head_at]
    body_rows = rows[head_at + 1 :] if header_rows else rows[1:]
    if not header_rows:
        head = [""] * width
        body_rows = rows
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    for r in body_rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out) + "\n\n"


def to_markdown(root: Node, heading_offset: int = 0) -> str:
    global _HEADING_OFFSET
    previous = _HEADING_OFFSET
    _HEADING_OFFSET = heading_offset
    try:
        md = _md_block(root)
    finally:
        _HEADING_OFFSET = previous
    # collapse 3+ blank lines
    lines = md.split("\n")
    out: list[str] = []
    blanks = 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks > 2:
                continue
        else:
            blanks = 0
        out.append(line.rstrip())
    return "\n".join(out).strip() + "\n"
