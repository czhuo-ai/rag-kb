"""模型调用层：OpenAI 兼容接口（默认智谱 open.bigmodel.cn），带重试与用量统计。"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .config import CACHE, CFG

CACHE.mkdir(parents=True, exist_ok=True)
EMB_CACHE = CACHE / "embedding.jsonl"


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, prompt: int, completion: int) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.calls += 1

    def as_dict(self) -> dict:
        return {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
        }


USAGE = Usage()


class LLMError(RuntimeError):
    pass


def _post(path: str, payload: dict, retries: int = 3) -> dict:
    url = f"{CFG.api_base}/{path.lstrip('/')}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {CFG.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=CFG.request_timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            last = LLMError(f"HTTP {exc.code}: {detail}")
            if exc.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise last
        except Exception as exc:  # 网络抖动
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise LLMError(f"请求失败: {last}")


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.2,
         max_tokens: int = 512, json_mode: bool = False) -> tuple[str, dict]:
    payload = {
        "model": model or CFG.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post("chat/completions", payload)
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    USAGE.add(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    return content, usage


_cache: dict[str, list[float]] = {}
if EMB_CACHE.exists():
    for line in EMB_CACHE.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
            _cache[rec["h"]] = rec["v"]
        except Exception:
            continue


def _hash(text: str) -> str:
    return hashlib.sha256((CFG.embed_model + "\x00" + text).encode("utf-8")).hexdigest()


def embed(texts: list[str], batch: int = 24) -> list[list[float]]:
    """带磁盘缓存的批量向量化，避免重复计费。"""
    out: list[list[float] | None] = [None] * len(texts)
    todo: list[int] = []
    for i, text in enumerate(texts):
        key = _hash(text)
        if key in _cache:
            out[i] = _cache[key]
        else:
            todo.append(i)

    for start in range(0, len(todo), batch):
        part = todo[start : start + batch]
        data = _post("embeddings", {"model": CFG.embed_model, "input": [texts[i] for i in part]})
        usage = data.get("usage", {})
        USAGE.add(usage.get("prompt_tokens", 0), 0)
        with EMB_CACHE.open("a", encoding="utf-8") as fh:
            for item, idx in zip(data["data"], part):
                vec = item["embedding"]
                out[idx] = vec
                _cache[_hash(texts[idx])] = vec
                fh.write(json.dumps({"h": _hash(texts[idx]), "v": vec}, ensure_ascii=False) + "\n")
    return [v or [0.0] * 2048 for v in out]
