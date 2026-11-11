"""三种切分策略：fixed / heading / semantic。

fixed    —— 按字符窗口滑动，最朴素，作为基线
heading  —— 先按标题分段，再在段内滑动，避免跨主题
semantic —— 句子级切片后按相邻句向量相似度聚合，主题变化处断开
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .extract import Parsed

SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


@dataclass
class Chunk:
    text: str
    heading: str
    doc: str
    ord: int


def _slide(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    step = max(1, size - overlap)
    out = []
    for start in range(0, len(text), step):
        piece = text[start : start + size].strip()
        if len(piece) < 40 and out:
            out[-1] += piece
            break
        if piece:
            out.append(piece)
        if start + size >= len(text):
            break
    return out


def chunk_fixed(parsed: Parsed, size: int, overlap: int) -> list[Chunk]:
    text = "\n".join(b.text for b in parsed.blocks)
    return [Chunk(t, "", parsed.name, i) for i, t in enumerate(_slide(text, size, overlap))]


def chunk_heading(parsed: Parsed, size: int, overlap: int) -> list[Chunk]:
    groups: list[tuple[str, list[str]]] = []
    heading = ""
    buf: list[str] = []
    for block in parsed.blocks:
        if block.level and block.level <= 3:
            if buf:
                groups.append((heading, buf))
            heading, buf = block.text, []
            continue
        if block.tag == "h1" or block.tag == "h2":
            continue
        buf.append(block.text)
    if buf:
        groups.append((heading, buf))
    if not groups:
        return chunk_fixed(parsed, size, overlap)

    chunks: list[Chunk] = []
    idx = 0
    for heading, lines in groups:
        body = "\n".join(lines)
        for piece in _slide(body, size, overlap):
            prefix = f"{heading}｜" if heading else ""
            chunks.append(Chunk(prefix + piece, heading, parsed.name, idx))
            idx += 1
    return chunks


def chunk_semantic(parsed: Parsed, size: int, overlap: int, embed_fn) -> list[Chunk]:
    """句级切片 + 相邻相似度断点。

    embed_fn: list[str] -> list[list[float]]
    """
    text = "\n".join(b.text for b in parsed.blocks)
    sents = [s.strip() for s in SENT_SPLIT.split(text) if len(s.strip()) >= 8]
    if not sents:
        return []
    if len(sents) == 1:
        return [Chunk(sents[0], "", parsed.name, 0)]

    vecs = embed_fn(sents)
    chunks: list[Chunk] = []
    cur: list[str] = [sents[0]]
    idx = 0
    for i in range(1, len(sents)):
        sim = _cos(vecs[i - 1], vecs[i])
        too_long = sum(len(x) for x in cur) > size
        if sim < 0.55 or too_long:
            text_ = "".join(cur).strip()
            if text_:
                chunks.append(Chunk(text_, "", parsed.name, idx))
                idx += 1
            tail = text_[-overlap:] if overlap else ""
            cur = [tail, sents[i]] if tail else [sents[i]]
        else:
            cur.append(sents[i])
    rest = "".join(cur).strip()
    if rest:
        chunks.append(Chunk(rest, "", parsed.name, idx))
    return chunks


def _cos(a: list[float], b: list[float]) -> float:
    import numpy as np

    va, vb = np.array(a, dtype="float32"), np.array(b, dtype="float32")
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if not na or not nb:
        return 0.0
    return float(va @ vb / (na * nb))
