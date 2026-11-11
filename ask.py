"""双击 .bat 用的简单入口。

用法：
  ask.py                 # 从环境变量 RAG_Q 读问题（由 命令行提问.bat 设置）
  ask.py --demo          # 跑三个示例问题
  ask.py "问题内容"       # 直接传问题（命令行里带引号）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.answer import answer as answer_fn  # noqa: E402
from app.cli import _load_index  # noqa: E402

DEMO = [
    "开宝箱要花多少字符数？宝箱最多存几个？",
    "BOSS 助手一天最多能打多少个招呼？打招呼语在哪里改？",
    "我这个账号的 B 站密码是多少？",
]


def show(question: str) -> None:
    index = _load_index()
    res = answer_fn(index, question, top_k=3, rerank="rrf")
    print("问：" + question)
    print()
    print("答：" + res.text)
    print()
    if res.citations:
        print("出处：")
        for c in res.citations:
            head = c["heading"] or "-"
            print(f"  [{c['n']}] {c['doc']} · {head}（相似度 {c['score']}）")
        print()
    print(f"耗时 {res.latency_ms} ms，token {res.usage.get('total_tokens', '?')}")


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "--demo":
        for i, q in enumerate(DEMO, 1):
            print("=" * 46)
            print(f" 第 {i} 个问题")
            print("=" * 46)
            show(q)
            print()
        return

    question = " ".join(argv).strip() or os.environ.get("RAG_Q", "").strip()
    if not question:
        question = DEMO[0]
    show(question)


if __name__ == "__main__":
    main()
