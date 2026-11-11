"""混合检索：BM25（字 bigram + 英文词）+ 向量召回，RRF 融合，可选 LLM 重排。"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

from .config import CFG
from .llm import chat, embed

TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> list[str]:
    raw = TOKEN_RE.findall(text.lower())
    grams: list[str] = []
    cjk_run: list[str] = []
    for tok in raw:
        if len(tok) == 1 and "\u4e00" <= tok <= "\u9fff":
            cjk_run.append(tok)
        else:
            if cjk_run:
                grams += _cjk_grams(cjk_run)
                cjk_run = []
            grams.append(tok)
    if cjk_run:
        grams += _cjk_grams(cjk_run)
    return grams


def _cjk_grams(chars: list[str]) -> list[str]:
    if len(chars) == 1:
        return chars
    return ["".join(chars[i : i + 2]) for i in range(len(chars) - 1)]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.docs = docs
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(1, self.N)
        self.tf = [Counter(d) for d in docs]
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(self.N, dtype="float32")
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = 0.0
            for t in query:
                f = tf.get(t)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / max(1, self.avgdl)))
            out[i] = s
        return out


class HybridIndex:
    def __init__(self, metas: list[dict], matrix: np.ndarray) -> None:
        self.metas = metas
        self.matrix = matrix
        self.bm25 = BM25([tokenize(m["text"]) for m in metas])

    def search(self, query: str, top_k: int | None = None, rerank: str | None = None) -> list[dict]:
        top_k = top_k or CFG.top_k
        rerank = rerank or CFG.rerank
        cand = min(CFG.candidate_k, len(self.metas))

        bm = self.bm25.scores(tokenize(query))
        qv = np.asarray(embed([query])[0], dtype="float32")
        qn = float(np.linalg.norm(qv)) or 1.0
        dense = self.matrix @ (qv / qn)

        bm_rank = np.argsort(-bm)[:cand]
        dn_rank = np.argsort(-dense)[:cand]

        fused: dict[int, float] = {}
        for rank, idx in enumerate(bm_rank):
            fused[int(idx)] = fused.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)
        for rank, idx in enumerate(dn_rank):
            fused[int(idx)] = fused.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)

        order = sorted(fused, key=lambda i: -fused[i])
        hits = [
            {
                **self.metas[i],
                "score": round(float(fused[i]), 6),
                "bm25": round(float(bm[i]), 3),
                "dense": round(float(dense[i]), 4),
            }
            for i in order[: cand]
        ]

        if rerank == "llm" and len(hits) > top_k:
            hits = self._llm_rerank(query, hits, top_k)
        return hits[:top_k]

    def _llm_rerank(self, query: str, hits: list[dict], top_k: int) -> list[dict]:
        listing = "\n".join(f"[{i}] {h['doc']}：{h['text'][:120]}" for i, h in enumerate(hits))
        prompt = (
            f"问题：{query}\n\n候选片段：\n{listing}\n\n"
            f"请按与问题的相关性排序，只输出最相关的前 {top_k} 个编号，用逗号分隔，不要解释。"
        )
        try:
            text, _ = chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=40)
            ids = [int(x) for x in re.findall(r"\d+", text)]
            picked, seen = [], set()
            for i in ids:
                if 0 <= i < len(hits) and i not in seen:
                    seen.add(i)
                    picked.append(hits[i])
            for i, h in enumerate(hits):
                if len(picked) >= top_k:
                    break
                if i not in seen:
                    picked.append(h)
            return picked[:top_k]
        except Exception:
            return hits[:top_k]
