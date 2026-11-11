"""HTTP 服务：FastAPI 暴露 /ask、/stats，附一个最小网页问答界面。

启动：
    python -m app.api          # 默认 8000
    uvicorn app.api:app --port 8000
"""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import store
from .answer import answer as answer_fn
from .config import INDEX
from .retrieve import HybridIndex

app = FastAPI(title="企业知识库问答", version="1.0.0")
_lock = threading.Lock()
_index: HybridIndex | None = None


def get_index() -> HybridIndex:
    global _index
    with _lock:
        if _index is None:
            if not INDEX.exists():
                raise HTTPException(503, "索引还没建，先跑 python -m app.cli ingest")
            metas, matrix = store.load_all(store.connect(INDEX))
            _index = HybridIndex(metas, matrix)
        return _index


def reload_index() -> None:
    global _index
    with _lock:
        _index = None


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
    rerank: str = Field(default="rrf", pattern="^(none|rrf|llm)$")


@app.get("/health")
def health() -> dict:
    ok = INDEX.exists()
    payload = {"status": "ok" if ok else "index_missing"}
    if ok:
        payload["stats"] = store.stats(store.connect(INDEX))
    return payload


@app.get("/stats")
def stats() -> dict:
    if not INDEX.exists():
        raise HTTPException(503, "索引不存在")
    return store.stats(store.connect(INDEX))


@app.post("/ask")
def ask(body: AskIn) -> dict:
    idx = get_index()
    res = answer_fn(idx, body.question, top_k=body.top_k, rerank=body.rerank)
    return {
        "answer": res.text,
        "refused": res.refused,
        "citations": res.citations,
        "latency_ms": res.latency_ms,
        "usage": res.usage,
    }


PAGE = """<!doctype html>
<meta charset="utf-8"><title>知识库问答</title>
<style>
 body{font:15px/1.7 -apple-system,"Segoe UI",sans-serif;max-width:760px;margin:48px auto;padding:0 20px;color:#1b1f24}
 h1{font-size:20px;font-weight:600}
 textarea{width:100%;height:76px;padding:10px;font:inherit;border:1px solid #d0d7de;border-radius:8px}
 button{margin-top:10px;padding:8px 18px;border:0;border-radius:8px;background:#1f6feb;color:#fff;font:inherit;cursor:pointer}
 .ans{margin-top:22px;padding:14px 16px;background:#f6f8fa;border-radius:10px;white-space:pre-wrap}
 .cite{margin-top:10px;font-size:13px;color:#57606a}
 .cite div{margin:2px 0}
</style>
<h1>企业知识库问答</h1>
<textarea id="q" placeholder="比如：宝箱多久攒一个？"></textarea>
<button onclick="go()">提问</button>
<div id="out"></div>
<script>
async function go(){
  const q=document.getElementById('q').value.trim(); if(!q) return;
  const out=document.getElementById('out'); out.innerHTML='思考中…';
  const t0=performance.now();
  const r=await fetch('/ask',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({question:q})});
  const d=await r.json();
  out.innerHTML=`<div class="ans">${d.answer.replace(/</g,'&lt;')}</div>`+
    `<div class="cite">${(d.citations||[]).map(c=>`[${c.n}] ${c.doc} ${c.heading||''}`).join('<br>')}</div>`+
    `<div class="cite">${Math.round(performance.now()-t0)} ms</div>`;
}
</script>"""


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE


def main() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
