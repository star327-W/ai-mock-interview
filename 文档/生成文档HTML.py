# -*- coding: utf-8 -*-
"""
把本目录下的 .md 文档重新排版成 .html。

为什么要有这个脚本：以前 HTML 是手工照着 md 排的，改完 md 忘了改 html，
两边内容就对不上了。现在 HTML 一律从 md 生成，改内容只改 .md，然后跑一次本脚本。

用法（在「文档」目录下）：
    python 生成文档HTML.py

依赖：只用 Python 标准库，不需要装任何东西。
"""
import html
import io
import os
import re

# 需要转换的文档：md 文件 → (html 文件, 副标题)
# 答辩材料已移到桌面「项目文档-学校材料」，仓库里只保留需求分析文档
JOBS = [
    ("模拟面试AI助手-需求分析文档.md", "模拟面试AI助手-需求分析文档.html",
     "需求梳理 + 实现情况对照"),
]

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    background: linear-gradient(160deg, #f3f7fd 0%, #eef4fb 50%, #f7f4f0 100%);
    color: #1a2230; line-height: 1.85; padding: 48px 24px;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header { text-align: center; margin-bottom: 32px; }
  h1 { font-size: 30px; color: #0e3f8c; margin-bottom: 10px; }
  .subtitle { color: #5a6a80; font-size: 14px; }
  nav.toc {
    background: #ffffff; border-radius: 12px; padding: 16px 22px; margin-bottom: 32px;
    border: 1px solid #e2e8f2; box-shadow: 0 2px 10px rgba(30,79,168,.05);
  }
  nav.toc h2 { font-size: 15px; color: #1e4fa8; margin-bottom: 8px; padding: 0;
    background: none; border: none; box-shadow: none; }
  nav.toc ul { list-style: none; display: flex; flex-wrap: wrap; gap: 8px 18px; }
  nav.toc a { color: #1e4fa8; text-decoration: none; font-size: 14px; border-bottom: 1px dashed #b9cbe8; }
  nav.toc a:hover { border-bottom-style: solid; }
  section { margin-bottom: 36px; }
  h2 {
    font-size: 21px; color: #0e3f8c; padding: 10px 16px; margin-bottom: 18px;
    background: #ffffff; border-radius: 10px; border: 1px solid #e2e8f2;
    box-shadow: 0 2px 8px rgba(30,79,168,.06);
  }
  h3 { font-size: 17px; color: #1e4fa8; margin: 22px 0 10px; }
  h4 { font-size: 15px; color: #2c3a50; margin: 16px 0 8px; }
  p { font-size: 14.5px; color: #2c3a50; margin-bottom: 10px; }
  ul, ol { margin: 8px 0 12px 22px; font-size: 14.5px; color: #2c3a50; }
  li { margin-bottom: 5px; }
  .qa {
    background: #ffffff; border-radius: 12px; padding: 18px 22px; margin-bottom: 14px;
    border: 1px solid #e5eaf3; box-shadow: 0 2px 10px rgba(30,79,168,.05);
  }
  .q { font-size: 16px; font-weight: bold; color: #1e4fa8; margin-bottom: 8px; }
  .a { font-size: 14.5px; color: #2c3a50; }
  .a b, .a strong, p b, p strong, li b, li strong, td b, td strong { color: #0e3f8c; }
  code {
    background: #eef2f9; padding: 1px 6px; border-radius: 4px;
    font-family: Consolas, monospace; font-size: 13px; color: #1e4fa8;
  }
  pre {
    background: #f4f7fc; border: 1px solid #e2e8f2; border-radius: 10px;
    padding: 14px 18px; margin: 12px 0; overflow-x: auto;
    font-family: Consolas, monospace; font-size: 13px; line-height: 1.65; color: #2c3a50;
  }
  pre code { background: none; padding: 0; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0 18px; font-size: 14px; }
  th, td { border: 1px solid #e2e8f2; padding: 8px 12px; text-align: left; vertical-align: top; }
  th { background: #e8eff8; color: #0e3f8c; font-weight: bold; }
  tr:nth-child(even) td { background: #fafcff; }
  hr { border: none; border-top: 1px dashed #cfd9e8; margin: 28px 0; }
  blockquote {
    background: #e8eff8; border-left: 4px solid #1e4fa8; border-radius: 8px;
    padding: 12px 18px; margin: 12px 0; font-size: 14px; color: #1a2230;
  }
  blockquote p:last-child { margin-bottom: 0; }
  footer { text-align: center; color: #8b97a8; font-size: 13px; margin-top: 40px; }
"""


def inline(t: str) -> str:
    """行内标记 → HTML（先转义再处理 ** 和 `）"""
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def convert(md: str):
    lines = md.split("\n")
    title = "文档"
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]

    body, toc = [], []
    i, in_code, code_buf, list_buf, ordered, table_buf = 0, False, [], [], False, []

    def flush_list():
        nonlocal list_buf, ordered
        if list_buf:
            tag = "ol" if ordered else "ul"
            body.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in list_buf) + f"</{tag}>")
            list_buf = []

    def flush_table():
        nonlocal table_buf
        if table_buf:
            rows = [r for r in table_buf if not re.match(r"^\|[\s:|-]+\|$", r)]
            out = ["<table>"]
            for n, r in enumerate(rows):
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                tag = "th" if n == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            out.append("</table>")
            body.append("".join(out))
            table_buf = []

    def flush_qa(question, ans_lines):
        body.append(
            f'<div class="qa"><div class="q">{html.escape(question)}</div>'
            f'<div class="a">{"<br>".join(inline(x) for x in ans_lines)}</div></div>'
        )

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        # 代码块
        if line.startswith("```"):
            if in_code:
                body.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf, in_code = [], False
            else:
                flush_list(); flush_table(); in_code = True
            i += 1; continue
        if in_code:
            code_buf.append(raw); i += 1; continue

        # 表格
        if line.startswith("|") and line.endswith("|"):
            flush_list(); table_buf.append(line); i += 1; continue
        flush_table()

        # 列表
        m_ul = re.match(r"^[-*]\s+(.*)$", line)
        m_ol = re.match(r"^\d+\.\s+(.*)$", line)
        if m_ul or m_ol:
            if not list_buf:
                ordered = bool(m_ol)
            list_buf.append(inline((m_ul or m_ol).group(1)))
            i += 1; continue
        flush_list()

        s = line.strip()
        if not s:
            i += 1; continue
        if s.startswith("---") or s.startswith("***"):
            body.append("<hr>"); i += 1; continue

        # 标题（### Q1：… 要先当问答块，别被通用标题规则吃掉）
        if not re.match(r"^#{3,4}\s*Q\d+[：:]", s):
            if s.startswith("#### "):
                body.append(f"<h4>{inline(s[5:])}</h4>"); i += 1; continue
            if s.startswith("### "):
                body.append(f"<h3>{inline(s[4:])}</h3>"); i += 1; continue
        if s.startswith("## "):
            txt = s[3:]
            anchor = f"sec-{len(toc) + 1}"
            toc.append((anchor, re.sub(r"[*`]", "", txt)))
            body.append(f'<section id="{anchor}"><h2>{inline(txt)}</h2>')
            i += 1; continue

        # 引用
        if s.startswith(">"):
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(inline(lines[i].strip().lstrip(">").strip()))
                i += 1
            body.append("<blockquote>" + "".join(f"<p>{x}</p>" for x in q if x) + "</blockquote>")
            continue

        # **Qn：…** 后面跟答案
        m_q = re.match(r"^\*\*(Q\d+[：:].*?)\*\*$", s)
        if m_q:
            question = m_q.group(1)
            i += 1
            ans = []
            while i < len(lines) and lines[i].strip() and not re.match(
                r"^(\*\*Q\d+[：:]|#{1,4}\s)", lines[i].strip()
            ):
                ans.append(lines[i].strip()); i += 1
            flush_qa(question, ans); continue

        # ### Qn：… 也当问答块
        m_q3 = re.match(r"^#{3,4}\s*(Q\d+[：:].*)$", s)
        if m_q3:
            question = m_q3.group(1)
            i += 1
            ans = []
            while i < len(lines) and lines[i].strip() and not re.match(
                r"^#{1,4}\s*\**Q?\d", lines[i].strip()
            ) and not lines[i].strip().startswith("## "):
                t = lines[i].strip()
                if t == "---":
                    break
                ans.append(t); i += 1
            flush_qa(question, ans); continue

        body.append(f"<p>{inline(s)}</p>")
        i += 1

    flush_list(); flush_table()
    if in_code and code_buf:
        body.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")

    opened = sum(1 for b in body if b.startswith("<section"))
    text = "\n".join(body) + ("</section>" * opened)

    nav = ""
    if len(toc) >= 5:
        items = "".join(f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc)
        nav = f'<nav class="toc"><h2>目录</h2><ul>{items}</ul></nav>'
    return title, nav, text


def build(base: str, src: str, dst: str, subtitle: str):
    md = io.open(os.path.join(base, src), encoding="utf-8").read()
    title, nav, body = convert(md)
    doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">{html.escape(subtitle)}</div>
  </header>
{nav}
{body}
  <footer>本页由同目录下的 Markdown 文档自动生成 · 改内容请改 .md，再跑一次 生成文档HTML.py</footer>
</div>
</body>
</html>
"""
    io.open(os.path.join(base, dst), "w", encoding="utf-8", newline="\n").write(doc)
    print(f"  已生成 {dst}  ({len(doc)} 字符)")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    print("从 Markdown 重新生成 HTML：")
    for s, d, sub in JOBS:
        if os.path.exists(os.path.join(here, s)):
            build(here, s, d, sub)
        else:
            print(f"  跳过（找不到 {s}）")
    print("完成。")
