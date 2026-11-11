"""回答生成：带引用的抽取式 + 生成式混合，低置信度时拒答。"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .config import CFG
from .llm import chat
from .retrieve import HybridIndex

SYSTEM = (
    "你是企业知识库问答助手。只能依据【资料】回答，不要使用资料以外的知识。\n"
    "规则：\n"
    "1. 每句结论后面用 [1][2] 标注依据的片段编号；\n"
    "2. 资料里没有的信息，直接回答「资料中没有找到相关内容」，不要猜测；\n"
    "3. 回答控制在 4 句以内，用中文。"
)


@dataclass
class Answer:
    text: str
    refused: bool
    citations: list[dict]
    latency_ms: int
    usage: dict


def build_context(hits: list[dict]) -> str:
    lines = []
    for i, h in enumerate(hits, 1):
        head = f"《{h['doc']}》" + (f" · {h['heading']}" if h.get("heading") else "")
        lines.append(f"[{i}] {head}\n{h['text']}")
    return "\n\n".join(lines)


def answer(index: HybridIndex, question: str, top_k: int | None = None,
           rerank: str | None = None, min_dense: float | None = None) -> Answer:
    started = time.time()
    hits = index.search(question, top_k=top_k, rerank=rerank)
    threshold = CFG.min_score if min_dense is None else min_dense
    best_dense = max((h["dense"] for h in hits), default=0.0)

    if not hits or best_dense < threshold:
        return Answer(
            text="资料中没有找到相关内容。",
            refused=True,
            citations=[],
            latency_ms=int((time.time() - started) * 1000),
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    prompt = f"【资料】\n{build_context(hits)}\n\n【问题】{question}\n\n请按规则作答。"
    text, usage = chat(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=400,
    )
    refused = "资料中没有找到相关内容" in text and len(text) < 40
    return Answer(
        text=text.strip(),
        refused=refused,
        citations=[{"n": i + 1, "doc": h["doc"], "heading": h["heading"], "score": h["score"]}
                   for i, h in enumerate(hits)],
        latency_ms=int((time.time() - started) * 1000),
        usage=usage or {},
    )
