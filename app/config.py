"""全局配置：模型接入、路径、检索参数。

所有值都可以用环境变量覆盖，默认值指向本机已验证可用的智谱 OpenAI 兼容接口。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CORPUS = DATA / "corpus"
INDEX = Path(os.getenv("RAG_INDEX", str(DATA / "index.sqlite")))
EVAL_DIR = ROOT / "eval"
CACHE = DATA / "cache"


def _load_key() -> str:
    key = os.getenv("LLM_API_KEY") or os.getenv("ZHIPU_API_KEY")
    if key:
        return key
    # 复用本机已有的 modlens 配置，省得再配一遍
    cfg = Path.home() / ".modlens" / "config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            return data["providers"]["openai"]["apiKey"]
        except Exception:
            pass
    return ""


class Config:
    api_base = os.getenv("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
    api_key = _load_key()
    embed_model = os.getenv("EMBED_MODEL", "embedding-3")
    llm_model = os.getenv("LLM_MODEL", "glm-4-air")

    # 切分
    chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
    chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "64"))
    chunk_strategy = os.getenv("CHUNK_STRATEGY", "fixed")  # fixed | heading | semantic

    # 检索
    top_k = int(os.getenv("TOP_K", "5"))
    candidate_k = int(os.getenv("CANDIDATE_K", "20"))
    rerank = os.getenv("RERANK", "rrf")  # none | rrf | llm
    min_score = float(os.getenv("MIN_SCORE", "0.30"))  # 低于该相似度直接拒答

    request_timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))


CFG = Config()
