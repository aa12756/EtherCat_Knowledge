# -*- coding: utf-8 -*-
"""把手册 MD 里的 ./images/*.png 嵌成 base64，生成单文件 HTML，便于复制到飞书云文档。

用法（在仓库根或本目录）：
    python build_feishu_html.py

输出：S7-1200真机联调与TIA操作手册-飞书粘贴版.html
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
MD = HERE / "S7-1200真机联调与TIA操作手册.md"
OUT = HERE / "S7-1200真机联调与TIA操作手册-飞书粘贴版.html"

IMG_RE = re.compile(r"!\[([^\]]*)\]\((\./images/[^)]+)\)")


def main() -> None:
    text = MD.read_text(encoding="utf-8")
    parts: list[str] = []
    last = 0
    for m in IMG_RE.finditer(text):
        parts.append(_md_chunk_to_html(text[last : m.start()]))
        alt, rel = m.group(1), m.group(2)
        img_path = HERE / rel.removeprefix("./")
        if not img_path.is_file():
            parts.append(f'<p style="color:red">[缺失图片: {rel}]</p>')
        else:
            b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
            parts.append(
                f'<figure><img alt="{_esc(alt)}" src="data:image/png;base64,{b64}" '
                f'style="max-width:100%;border:1px solid #ddd"/><figcaption>{_esc(alt)}</figcaption></figure>'
            )
        last = m.end()
    parts.append(_md_chunk_to_html(text[last:]))
    body = "\n".join(parts)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/>
<title>S7-1200 真机联调与 TIA 操作手册（飞书粘贴版）</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;line-height:1.6;padding:0 16px}}
h1,h2,h3{{margin-top:1.2em}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #ccc;padding:6px 10px}}
code{{background:#f4f4f4;padding:2px 4px}}
figure{{margin:16px 0}} figcaption{{font-size:0.9em;color:#555}}
blockquote{{border-left:4px solid #ccc;margin:0;padding-left:12px;color:#444}}
</style></head><body>
<p><em>生成说明：用浏览器打开本文件 → 全选复制 → 粘贴到飞书云文档。勿直接导入 .md（飞书不识别 ./images 相对路径）。</em></p>
{body}
</body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"已生成: {OUT}")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def _md_chunk_to_html(chunk: str) -> str:
    """极简 MD→HTML（仅用于手册结构；复杂语法仍以原 MD 在本地看）。"""
    if not chunk.strip():
        return ""
    lines = chunk.split("\n")
    out: list[str] = []
    in_code = False
    in_table = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                out.append("</code></pre>")
                in_code = False
            else:
                out.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            out.append(_esc(line))
            continue
        if line.strip().startswith("|") and "|" in line[1:]:
            if not in_table:
                out.append("<table>")
                in_table = True
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            tag = "th" if not out[-1].endswith("</tr>") and "<table>" in out[-1] else "td"
            if tag == "th":
                out.append("<tr>" + "".join(f"<th>{_esc(c)}</th>" for c in cells) + "</tr>")
            else:
                out.append("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if line.startswith("# "):
            out.append(f"<h1>{_inline(_esc(line[2:].strip()))}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_inline(_esc(line[3:].strip()))}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{_inline(_esc(line[4:].strip()))}</h3>")
        elif line.startswith("#### "):
            out.append(f"<h4>{_inline(_esc(line[5:].strip()))}</h4>")
        elif line.startswith("> "):
            out.append(f"<blockquote>{_inline(_esc(line[2:].strip()))}</blockquote>")
        elif line.strip() == "---":
            out.append("<hr/>")
        elif line.strip() == "":
            out.append("<br/>")
        elif line.strip().startswith("- "):
            out.append(f"<li>{_inline(_esc(line.strip()[2:]))}</li>")
        else:
            out.append(f"<p>{_inline(_esc(line))}</p>")
    if in_table:
        out.append("</table>")
    if in_code:
        out.append("</code></pre>")
    return "\n".join(out)


def _inline(s: str) -> str:
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        s,
    )
    return s


if __name__ == "__main__":
    main()