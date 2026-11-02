"""
简历文本解析：PDF / Word(docx) / TXT
上传后同步解析，成功 parse_status=2，失败 parse_status=3。

两级解析：
  1. extract_text  —— 把文件读成纯文本（PDF 用 pypdf，docx 直接解析 XML，纯本地）
  2. parse_struct  —— 调大模型把纯文本拆成结构化字段（姓名/技能/项目经历…）
                     失败返回 None，不影响上传，面试时自动退回纯文本
"""
import io


def extract_text(filename: str, content: bytes) -> str | None:
    """根据扩展名分发解析，返回纯文本（失败返回 None）"""
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    try:
        if ext == "pdf":
            return _pdf(content)
        if ext in ("doc", "docx"):
            text = _docx(content)
            if text is None and ext == "doc":
                # 老 .doc 格式兜底：按二进制宽松提取可读字符
                return _doc_fallback(content)
            return text
        if ext == "txt":
            return content.decode("utf-8", errors="ignore").strip() or None
        return None
    except Exception:
        return None


def _pdf(content: bytes) -> str | None:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(p for p in pages if p.strip()).strip()
    return text or None


# OOXML 命名空间（docx 本质是个 zip，正文在 word/document.xml）
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(content: bytes) -> str | None:
    """
    提取 docx 文本（zip + 解析 document.xml）。

    为什么不用 python-docx 的 paragraphs/tables：
    中文简历模板几乎都用「文本框」排版，文本框内容在 XML 里是 *嵌套在其他段落内部* 的
    段落，python-docx 完全读不到 —— 一份简历会只解析出零头。这里按文档顺序遍历，
    遇到段落就断行、遇到 w:t 就取字，正文 / 文本框 / 表格一律覆盖。
    """
    import zipfile
    from xml.etree import ElementTree as ET

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError):
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    lines: list[str] = []
    buf: list[str] = []
    # iter() 是文档顺序的先序遍历：文本框里的段落会紧跟其宿主段落出现
    for node in root.iter():
        if node.tag == f"{_W}p":
            line = "".join(buf).strip()
            if line:
                lines.append(line)
            buf = []
        elif node.tag == f"{_W}t":
            if node.text:
                buf.append(node.text)
    line = "".join(buf).strip()
    if line:
        lines.append(line)

    text = "\n".join(lines).strip()
    return text or None


def _doc_fallback(content: bytes) -> str | None:
    """老版 .doc 无官方解析库，宽松提取可读文本段（CJK + ASCII 可打印字符）"""
    import re

    raw = content.decode("gbk", errors="ignore")
    # 保留含中文或字母数字的行，过滤乱码
    lines = [
        ln.strip()
        for ln in raw.splitlines()
        if re.search(r"[\u4e00-\u9fff]", ln) or re.search(r"[A-Za-z0-9 .,/#&()-]{6,}", ln)
    ]
    text = "\n".join(lines).strip()
    return text or None


# ========================================================================
# \u7ed3\u6784\u5316\u89e3\u6790\uff1a\u7eaf\u6587\u672c \u2192 \u5b57\u6bb5\uff08\u59d3\u540d / \u6280\u80fd / \u9879\u76ee\u7ecf\u5386 \u2026\uff09
# ========================================================================

_STRUCT_PROMPT = """\u4f60\u662f\u7b80\u5386\u4fe1\u606f\u62bd\u53d6\u5f15\u64ce\u3002\u8bf7\u4ece\u4e0b\u9762\u7684\u7b80\u5386\u6587\u672c\u4e2d\u62bd\u53d6\u7ed3\u6784\u5316\u4fe1\u606f\uff0c\u53ea\u8f93\u51fa JSON\u3002

\u62bd\u53d6\u8981\u6c42\uff1a
1. \u53ea\u62bd\u7b80\u5386\u91cc**\u771f\u5b9e\u5199\u5230**\u7684\u5185\u5bb9\uff0c\u4e00\u4e2a\u5b57\u90fd\u4e0d\u8981\u7f16\u9020\u6216\u63a8\u6d4b\u3002\u6ca1\u6709\u7684\u5b57\u6bb5\u586b\u7a7a\u5b57\u7b26\u4e32 "" \u6216\u7a7a\u6570\u7ec4 []\u3002
2. projects \u662f\u6700\u91cd\u8981\u7684\u5b57\u6bb5\uff0c\u8981\u5c3d\u91cf\u62bd\u5168\uff1a\u9879\u76ee\u540d\u79f0\u3001\u5019\u9009\u4eba\u62c5\u4efb\u7684\u89d2\u8272\u3001\u8d77\u6b62\u65f6\u95f4\u3001
   \u5177\u4f53\u505a\u4e86\u4ec0\u4e48\u3001\u7528\u4e86\u4ec0\u4e48\u6280\u672f\u3002
3. \u65f6\u95f4\u7edf\u4e00\u5199\u6210 YYYY.MM\uff08\u5982 2024.03\uff09\uff1b\u53ea\u6709\u5e74\u4efd\u5c31\u5199 YYYY\u3002
4. description \u538b\u7f29\u6210 1-3 \u53e5\uff0c**\u4fdd\u7559\u539f\u6587\u91cc\u7684\u91cf\u5316\u6210\u679c**\uff08\u5982"\u63a5\u53e3\u54cd\u5e94\u65f6\u95f4\u964d\u4f4e\u56db\u6210"\uff09\u3002
5. skills \u53ea\u62bd\u660e\u786e\u63d0\u5230\u7684\u6280\u672f/\u5de5\u5177/\u8f6f\u4ef6\uff0c\u4e0d\u8981\u8111\u8865\u3002

\u8f93\u51fa JSON\uff08\u4e25\u683c\u6309\u8fd9\u4e2a\u7ed3\u6784\uff09\uff1a
{
  "name": "\u59d3\u540d",
  "education": "\u5b66\u5386\uff0c\u5982 \u672c\u79d1 / \u7855\u58eb / \u5927\u4e13",
  "school": "\u5b66\u6821\u540d\u79f0",
  "major": "\u4e13\u4e1a",
  "graduation_year": "\u6bd5\u4e1a\u5e74\u4efd",
  "skills": ["\u6280\u80fd1", "\u6280\u80fd2"],
  "certificates": ["\u8bc1\u4e661"],
  "projects": [
    {"project_name": "\u9879\u76ee\u540d", "role": "\u62c5\u4efb\u7684\u89d2\u8272", "start_date": "2024.01",
     "end_date": "2024.12", "description": "\u505a\u4e86\u4ec0\u4e48\uff0c1-3 \u53e5", "tech_stack": "\u6280\u672f\u6808"}
  ],
  "internships": [
    {"company": "\u516c\u53f8", "role": "\u5c97\u4f4d", "start_date": "", "end_date": "", "description": ""}
  ],
  "highlights": ["\u7b80\u5386\u91cc\u6700\u7a81\u51fa\u7684 2-4 \u4e2a\u4eae\u70b9"]
}

\u7b80\u5386\u6587\u672c\uff1a
---"""


def _as_str(value) -> str:
    """\u4efb\u610f\u503c \u2192 \u53bb\u7a7a\u767d\u7684\u5b57\u7b26\u4e32"""
    if value is None:
        return ""
    return str(value).strip()


def _as_list(value) -> list:
    """\u4efb\u610f\u503c \u2192 \u5b57\u7b26\u4e32\u5217\u8868\uff08\u6a21\u578b\u5076\u5c14\u4f1a\u8fd4\u56de\u5355\u4e2a\u5b57\u7b26\u4e32\u800c\u975e\u6570\u7ec4\uff09"""
    if isinstance(value, list):
        return [_as_str(v) for v in value if _as_str(v)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_struct(raw: dict) -> dict:
    """
    \u628a\u6a21\u578b\u8f93\u51fa\u89c4\u8303\u5316\u6210\u56fa\u5b9a\u7ed3\u6784\uff0c\u5e76\u6309\u6570\u636e\u5e93\u5217\u5bbd\u622a\u65ad\u3002
    \u6a21\u578b\u53ef\u80fd\u5c11\u7ed9\u5b57\u6bb5\u3001\u7ed9\u9519\u7c7b\u578b\uff0c\u8fd9\u91cc\u7edf\u4e00\u515c\u4f4f\uff0c\u4fdd\u8bc1\u4e0b\u6e38\u4e0d\u7528\u505a\u9632\u5fa1\u6027\u5224\u65ad\u3002
    """
    projects = []
    for p in (raw.get("projects") or []):
        if not isinstance(p, dict):
            continue
        name = _as_str(p.get("project_name"))
        if not name:
            continue  # \u9879\u76ee\u540d\u662f\u5fc5\u586b\u5217\uff0c\u7a7a\u7684\u76f4\u63a5\u4e22
        projects.append({
            "project_name": name[:128],
            "role": _as_str(p.get("role"))[:64],
            "start_date": _as_str(p.get("start_date"))[:16],
            "end_date": _as_str(p.get("end_date"))[:16],
            "description": _as_str(p.get("description")),
            "tech_stack": _as_str(p.get("tech_stack"))[:512],
        })

    internships = []
    for it in (raw.get("internships") or []):
        if not isinstance(it, dict):
            continue
        company = _as_str(it.get("company"))
        if not company:
            continue
        internships.append({
            "company": company[:128],
            "role": _as_str(it.get("role"))[:64],
            "start_date": _as_str(it.get("start_date"))[:16],
            "end_date": _as_str(it.get("end_date"))[:16],
            "description": _as_str(it.get("description")),
        })

    return {
        "name": _as_str(raw.get("name"))[:64],
        "education": _as_str(raw.get("education"))[:64],
        "school": _as_str(raw.get("school"))[:128],
        "major": _as_str(raw.get("major"))[:128],
        "graduation_year": _as_str(raw.get("graduation_year"))[:16],
        "skills": _as_list(raw.get("skills"))[:30],
        "certificates": _as_list(raw.get("certificates"))[:20],
        "projects": projects[:10],
        "internships": internships[:10],
        "highlights": _as_list(raw.get("highlights"))[:6],
    }


def parse_struct(text: str, *, timeout: int = 40) -> dict | None:
    """
    \u8c03\u5927\u6a21\u578b\u628a\u7b80\u5386\u7eaf\u6587\u672c\u62c6\u6210\u7ed3\u6784\u5316\u5b57\u6bb5\u3002

    \u4efb\u4f55\u5931\u8d25\uff08\u6ca1\u914d Key / \u8d85\u65f6 / \u6a21\u578b\u8fd4\u56de\u4e0d\u662f JSON\uff09\u90fd\u8fd4\u56de None\uff0c
    \u7531\u8c03\u7528\u65b9\u51b3\u5b9a\u9000\u56de\u7eaf\u6587\u672c \u2014\u2014 \u89e3\u6790\u5931\u8d25\u7edd\u4e0d\u80fd\u8ba9\u4e0a\u4f20\u5931\u8d25\u3002
    """
    if not text or not text.strip():
        return None
    try:
        from app.services.llm import chat_json, llm_enabled

        if not llm_enabled():
            return None
        from app.services.prompt_guard import UNTRUSTED_NOTE, wrap_untrusted

        result = chat_json(
            # \u7528\u5b57\u7b26\u4e32\u62fc\u63a5\u800c\u4e0d\u662f % \u683c\u5f0f\u5316\uff1a\u7b80\u5386/\u63d0\u793a\u8bcd\u91cc\u51fa\u73b0 % \u4e5f\u4e0d\u4f1a\u70b8
            [{"role": "user", "content": _STRUCT_PROMPT + UNTRUSTED_NOTE + wrap_untrusted(text, 4000)}],
            temperature=0.1,   # \u62bd\u53d6\u4efb\u52a1\u8981\u7a33\u5b9a\uff0c\u4e0d\u8981\u53d1\u6325
            max_tokens=2000,
            timeout=timeout,
        )
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    normalized = _normalize_struct(result)
    # \u4ec0\u4e48\u90fd\u6ca1\u62bd\u5230\uff0c\u89c6\u540c\u5931\u8d25\uff0c\u8ba9\u4e0a\u5c42\u9000\u56de\u7eaf\u6587\u672c
    if not any([normalized["skills"], normalized["projects"],
                normalized["internships"], normalized["highlights"]]):
        return None
    return normalized
