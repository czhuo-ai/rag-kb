"""不依赖网络与模型 key 的单元测试：切分与 BM25 行为。

跑法：
    python -m pytest -q          （或 python -m unittest discover -s tests -v）
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.chunk import chunk_fixed, chunk_heading  # noqa: E402
from app.extract import Block, Parsed  # noqa: E402
from app.retrieve import BM25, tokenize  # noqa: E402


def make_parsed() -> Parsed:
    p = Parsed(name="t.md", path="t.md", kind="markdown")
    p.blocks = [
        Block("开宝箱规则", heading="开宝箱规则", level=1, tag="h1"),
        Block("每累计 30 分钟活跃时间生成 1 个宝箱。", heading="开宝箱规则", tag="p"),
        Block("每次开箱消耗 1000 字符数，最多存 2 个。", heading="开宝箱规则", tag="p"),
        Block("私信回复", heading="私信回复", level=1, tag="h1"),
        Block("调度器每 20 秒轮询一次私信。", heading="私信回复", tag="p"),
    ]
    return p


class TestChunk(unittest.TestCase):
    def test_fixed_respects_size(self):
        chunks = chunk_fixed(make_parsed(), size=40, overlap=8)
        self.assertGreaterEqual(len(chunks), 2)
        # _slide 会把不足 40 字的尾巴并进上一块，所以上限是 size + 40
        for c in chunks:
            self.assertLessEqual(len(c.text), 80)
        joined = "".join(c.text for c in chunks)
        self.assertIn("开宝箱规则", joined)

    def test_heading_keeps_title_prefix(self):
        chunks = chunk_heading(make_parsed(), size=60, overlap=8)
        self.assertTrue(all("｜" in c.text for c in chunks))
        joined = "\n".join(c.text for c in chunks)
        self.assertIn("开宝箱规则", joined)
        self.assertIn("私信回复", joined)
        self.assertEqual({c.heading for c in chunks}, {"开宝箱规则", "私信回复"})

    def test_heading_chunks_do_not_mix_sections(self):
        chunks = chunk_heading(make_parsed(), size=60, overlap=8)
        for c in chunks:
            if c.heading == "私信回复":
                self.assertNotIn("宝箱", c.text)


class TestBM25(unittest.TestCase):
    def test_tokenize_cjk_bigrams(self):
        toks = tokenize("开宝箱")
        self.assertIn("开宝", toks)
        self.assertIn("宝箱", toks)

    def test_ranks_matching_doc_first(self):
        docs = [
            "每累计 30 分钟活跃时间生成 1 个宝箱",
            "调度器每 20 秒轮询一次私信",
            "宝箱每次开箱消耗 1000 字符数",
        ]
        bm = BM25([tokenize(d) for d in docs])
        scores = bm.scores(tokenize("宝箱 开箱 字符数"))
        self.assertEqual(max(range(3), key=lambda i: scores[i]), 2)

    def test_idf_prefers_rare_term(self):
        docs = ["私信 轮询", "私信 推送", "私信 宝箱"]
        bm = BM25([tokenize(d) for d in docs])
        scores = bm.scores(tokenize("宝箱"))
        self.assertGreater(scores[2], scores[0])


if __name__ == "__main__":
    unittest.main()
