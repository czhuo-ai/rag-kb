"""文档解析：PDF / DOCX / Markdown / TXT → 纯文本。

PDF 走 pdf-parse（node），因为本机没有 PyMuPDF/pypdf；
DOCX 走 python-docx，保留标题层级；Markdown/TXT 直接读。
每个文件返回带结构的段落列表，供切分阶段使用。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
NODE = os.environ.get("NODE_BIN") or "node"
PDF_SCRIPT = WORKSPACE / "scripts" / "pdf2txt.mjs"


@dataclass
class Block:
    text: str
    heading: str = ""      # 最近的标题（用于 heading 切分和引用定位）
    level: int = 0         # 标题层级，0 表示正文
    tag: str = "p"         # p / h1 / h2 / li / table


@dataclass
class Parsed:
    name: str
    path: str
    kind: str
    blocks: list[Block] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse_markdown(path: Path) -> Parsed:
    parsed = Parsed(name=path.name, path=str(path), kind="markdown")
    heading = ""
    for line in _read_text(path).splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            level = len(m.group(1))
            heading = m.group(2).strip()
            parsed.blocks.append(Block(text=heading, heading=heading, level=level, tag=f"h{level}"))
            continue
        tag = "li" if re.match(r"^([-*+]|\d+[.)])\s+", s) else "p"
        if s.startswith("|") and s.endswith("|"):
            tag = "table"
        parsed.blocks.append(Block(text=s, heading=heading, tag=tag))
    return parsed


def parse_docx(path: Path) -> Parsed:
    import docx  # python-docx

    parsed = Parsed(name=path.name, path=str(path), kind="docx")
    document = docx.Document(str(path))
    heading = ""
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading") or style.startswith("标题"):
            level = 1
            m = re.search(r"(\d+)", style)
            if m:
                level = int(m.group(1))
            heading = text
            parsed.blocks.append(Block(text=text, heading=heading, level=level, tag=f"h{level}"))
        else:
            parsed.blocks.append(Block(text=text, heading=heading, tag="p"))
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parsed.blocks.append(Block(text=" | ".join(cells), heading=heading, tag="table"))
    return parsed


def parse_pdf(path: Path) -> Parsed:
    """调用 node 的 pdf-parse 抽文本（本机没有 python 版 PDF 库）。

    脚本必须落在仓库根目录：ESM 的包解析看的是脚本所在目录，不是 cwd，
    放在 data/tmp 下会报 ERR_MODULE_NOT_FOUND。
    """
    run_dir = WORKSPACE / "data" / "tmp"
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / (path.stem + ".txt")
    script = WORKSPACE / ".pdf2txt.mjs"
    script.write_text(
        "import fs from 'node:fs'\n"
        "import { PDFParse } from 'pdf-parse'\n"
        "const buf = fs.readFileSync(process.argv[2])\n"
        "const parser = new PDFParse({ data: buf })\n"
        "const r = await parser.getText()\n"
        "fs.writeFileSync(process.argv[3], r.text)\n",
        encoding="utf-8",
    )
    try:
        proc = subprocess.run(
            [NODE, str(script), str(path), str(out)],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=180,
        )
    finally:
        script.unlink(missing_ok=True)
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError(f"PDF 解析失败: {proc.stderr[-300:]}")
    text = out.read_text(encoding="utf-8", errors="replace")
    parsed = Parsed(name=path.name, path=str(path), kind="pdf")
    for line in text.splitlines():
        s = line.strip()
        if s:
            parsed.blocks.append(Block(text=s))
    return parsed


def parse_any(path: Path) -> Parsed:
    suffix = path.suffix.lower()
    if suffix in (".md", ".markdown", ".txt"):
        return parse_markdown(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".pdf":
        return parse_pdf(path)
    raise ValueError(f"不支持的格式: {path.name}")


def dump(path: Path, parsed: Parsed) -> None:
    payload = {
        "name": parsed.name,
        "kind": parsed.kind,
        "chars": len(parsed.text),
        "blocks": [b.__dict__ for b in parsed.blocks],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
