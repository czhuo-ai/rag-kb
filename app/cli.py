"""命令行入口：ingest / search / ask / eval / stats。"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import store
from .answer import answer as answer_fn
from .chunk import chunk_fixed, chunk_heading, chunk_semantic
from .config import CFG, CORPUS, EVAL_DIR, INDEX
from .extract import parse_any
from .llm import USAGE, embed
from .retrieve import HybridIndex


def cmd_ingest(args: argparse.Namespace) -> None:
    conn = store.connect(Path(args.db) if args.db else INDEX)
    store.reset(conn)
    files = sorted([p for p in CORPUS.iterdir() if p.is_file()])
    strategy = args.strategy or CFG.chunk_strategy
    total_chunks = 0
    started = time.time()
    for path in files:
        try:
            parsed = parse_any(path)
        except Exception as exc:
            print(f"跳过 {path.name}: {exc}")
            continue
        if strategy == "fixed":
            chunks = chunk_fixed(parsed, CFG.chunk_size, CFG.chunk_overlap)
        elif strategy == "heading":
            chunks = chunk_heading(parsed, CFG.chunk_size, CFG.chunk_overlap)
        else:
            chunks = chunk_semantic(parsed, CFG.chunk_size, CFG.chunk_overlap, embed)
        if not chunks:
            continue
        vectors = embed([c.text for c in chunks])
        store.add_doc(conn, parsed.name, parsed.kind, len(parsed.text), chunks, vectors, strategy)
        total_chunks += len(chunks)
        print(f"{parsed.name:<34} {parsed.kind:<8} {len(parsed.text):>7} 字 → {len(chunks):>4} 片")
    stats = store.stats(conn)
    print(f"\n完成：{stats['docs']} 个文档 / {stats['chunks']} 片，用时 {time.time() - started:.1f}s")
    print(f"平均每片 {stats['avg_chunk_chars']} 字；embedding 用量 {USAGE.as_dict()}")


def _load_index(db: str | None = None) -> HybridIndex:
    conn = store.connect(Path(db) if db else INDEX)
    metas, matrix = store.load_all(conn)
    return HybridIndex(metas, matrix)


def cmd_search(args: argparse.Namespace) -> None:
    index = _load_index(args.db)
    for h in index.search(args.query, top_k=args.top_k, rerank=args.rerank):
        head = h["heading"][:20] if h["heading"] else "-"
        print(f"[{h['score']:.4f}] {h['doc']}｜{head}｜dense={h['dense']} bm25={h['bm25']}")
        print("   ", h["text"][:110].replace("\n", " "))


def cmd_ask(args: argparse.Namespace) -> None:
    index = _load_index(args.db)
    res = answer_fn(index, args.question, top_k=args.top_k, rerank=args.rerank)
    print(res.text)
    if res.citations:
        print("\n引用：")
        for c in res.citations:
            print(f"  [{c['n']}] {c['doc']} {c['heading']} ({c['score']})")
    print(f"\n耗时 {res.latency_ms} ms，用量 {res.usage}")


def _coverage(answer_text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    hit = sum(1 for k in keywords if k.lower() in answer_text.lower())
    return hit / len(keywords)


def cmd_eval(args: argparse.Namespace) -> None:
    """跑评测集，输出 recall@k / MRR / 答案要点覆盖率 / 拒答正确率 / 延迟。"""
    index = _load_index(args.db)
    questions = [json.loads(line) for line in (EVAL_DIR / "questions.jsonl").read_text("utf-8").splitlines() if line.strip()]
    rows, lat, tokens = [], [], {"prompt": 0, "completion": 0}
    hits_at_k = mrr = 0.0
    cov_sum = 0.0
    answerable = 0
    refuse_ok = refuse_total = 0

    for q in questions:
        res = answer_fn(index, q["q"], top_k=args.top_k, rerank=args.rerank)
        docs = [c["doc"] for c in res.citations]
        lat.append(res.latency_ms)
        tokens["prompt"] += res.usage.get("prompt_tokens", 0)
        tokens["completion"] += res.usage.get("completion_tokens", 0)

        if q["answerable"]:
            answerable += 1
            gold = q["gold_docs"]
            if any(d in docs[: args.top_k] for d in gold):
                hits_at_k += 1
            for rank, d in enumerate(docs[:10], 1):
                if d in gold:
                    mrr += 1.0 / rank
                    break
            cov = _coverage(res.text, q.get("keywords", []))
            cov_sum += cov
            rows.append({"q": q["q"], "hit": any(d in docs[: args.top_k] for d in gold), "coverage": cov,
                         "refused": res.refused, "answer": res.text[:80]})
        else:
            refuse_total += 1
            if res.refused:
                refuse_ok += 1
            rows.append({"q": q["q"], "hit": None, "coverage": None, "refused": res.refused,
                         "answer": res.text[:80]})

    n = max(1, answerable)
    metrics = {
        "questions": len(questions),
        "answerable": answerable,
        "recall_at_k": round(hits_at_k / n, 4),
        "mrr_at_10": round(mrr / n, 4),
        "keyword_coverage": round(cov_sum / n, 4),
        "refusal_accuracy": round(refuse_ok / max(1, refuse_total), 4),
        "refusal_cases": refuse_total,
        "latency_p50_ms": int(sorted(lat)[len(lat) // 2]) if lat else 0,
        "latency_p95_ms": int(sorted(lat)[min(len(lat) - 1, int(len(lat) * 0.95))]) if lat else 0,
        "tokens": tokens,
        "top_k": args.top_k,
        "rerank": args.rerank or CFG.rerank,
        "strategy": CFG.chunk_strategy,
    }
    out = Path(args.out) if args.out else EVAL_DIR / "report.json"
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    print(f"\n明细已写入 {out}")


def cmd_stats(args: argparse.Namespace) -> None:
    conn = store.connect(Path(args.db) if args.db else INDEX)
    print(json.dumps(store.stats(conn), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="rag-kb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("ingest")
    p.add_argument("--strategy", choices=["fixed", "heading", "semantic"])
    p.add_argument("--db")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("--top-k", type=int, default=CFG.top_k)
    p.add_argument("--rerank", choices=["none", "rrf", "llm"])
    p.add_argument("--db")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--top-k", type=int, default=CFG.top_k)
    p.add_argument("--rerank", choices=["none", "rrf", "llm"])
    p.add_argument("--db")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("eval")
    p.add_argument("--top-k", type=int, default=CFG.top_k)
    p.add_argument("--rerank", choices=["none", "rrf", "llm"])
    p.add_argument("--db")
    p.add_argument("--out")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("stats")
    p.add_argument("--db")
    p.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
