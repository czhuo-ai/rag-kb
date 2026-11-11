# 企业知识库问答（RAG 全链路）· 个人项目

一个能真正跑起来的检索增强问答系统：把本机 16 份中文文档（Markdown / DOCX / PDF）切分、向量化、
建立 BM25 + 向量混合索引，回答问题时给出带编号的引用，检索不到就明确拒答，并自带一套 38 题的评测脚本。

## 一句话结果

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 语料 | 16 个文档 / 270 个片段 | 标题切分后平均 305 字 |
| 评测集 | 38 题（30 可答 + 8 不可答） | 人工标注 gold 文档与关键词 |
| 召回 recall@5 | **96.7%** | 30 题里 29 题命中正确文档 |
| 排序 MRR@10 | **86.7%** | |
| 关键词覆盖率 | **77.8%** | 答案里应出现的关键数字/术语 |
| 拒答正确率 | **100%（8/8）** | 资料里没有的问题一律拒答 |
| 延迟 p50 / p95 | **0.60 s / 1.59 s** | top_k=3，本机 |
| 单次 prompt tokens | 约 700 | top_k=3 |

## 为什么这样设计

- **切分按标题走**：固定长度切分把表格和列表拦腰截断，标题切分（`标题｜正文` 前缀）在同样
  40 万 token 预算内把 MRR 从 84.4% 提到 86.7%，覆盖率从 68.9% 提到 77.8%。
- **BM25 与向量做 RRF 融合**：中文用 bigram 分词兜住专有名词，向量负责同义改写；
  融合用 RRF（k=60），不需要调权重。
- **拒答靠阈值 + 提示词双保险**：最高向量相似度低于 0.30 直接拒答，剩下的交给提示词约束。
- **评测先行**：每个改动都在同一套 38 题上跑，报告落在 `eval/report-*.json`。

## 实测对比（同一评测集）

| 配置 | recall@5 | MRR@10 | 覆盖率 | p50 |
| --- | --- | --- | --- | --- |
| 固定长度 512/64 + RRF | 96.7% | 84.4% | 68.9% | 1.98 s |
| 标题切分 + RRF | 96.7% | 86.7% | 77.8% | 1.25 s |
| 标题切分 + 不融合（纯向量排序） | 96.7% | 86.7% | 77.8% | 0.69 s |
| 标题切分 + 模型重排 | 93.3% | 86.7% | 75.6% | 1.34 s |
| 语义切分 + RRF | 90.0% | 74.7% | 61.1% | 1.12 s |
| 标题切分 + RRF + top_k=3 | 96.7% | 86.7% | 71.1% | 0.60 s |

两条如实的负结果：语义切分在这套中文文档上反而更差（会把表格和步骤拆碎）；
模型重排没提升质量却多了 1 秒延迟，所以默认关掉。

## 目录

```
app/config.py    配置（模型、切分、阈值，key 读 ~/.modlens/config.json）
app/extract.py   Markdown / DOCX / PDF 解析（PDF 走 node pdf-parse）
app/chunk.py     固定长度 / 标题 / 语义三种切分
app/store.py     SQLite 存文档、片段、向量（float32 BLOB）
app/retrieve.py  BM25 + 向量 + RRF 混合检索
app/answer.py    提示词、引用拼接、拒答
app/cli.py       ingest / search / ask / eval / stats
app/api.py       FastAPI：/ask /stats /health + 网页问答页
eval/            38 题评测集与各配置的评测报告
```

## 跑起来

**环境**：Python 3.11+、Node 18+（只有解析 PDF 时用到）、一个 OpenAI 兼容的对话 + 向量接口。
本项目实测用的是智谱 `glm-4-air`（对话）与 `embedding-3`（2048 维向量）。

```bash
# 1) Python 依赖
pip install -r requirements.txt

# 2) PDF 解析依赖（只有语料里有 PDF 才需要）
npm install

# 3) 配置 key（也可以写在 ~/.modlens/config.json 里作为回退）
export ZHIPU_API_KEY=你的key          # Windows: set ZHIPU_API_KEY=...

# 4) 建索引并提问
python -m app.cli ingest --strategy heading --db data/index-heading.sqlite
python -m app.cli ask "宝箱多久生成一个？开箱代价是什么？" --db data/index-heading.sqlite

# 5) 复现上面的评测表
python -m app.cli eval --db data/index-heading.sqlite --out eval/report-heading-rrf.json

# 6) 起个网页问答页
python -m app.api            # http://127.0.0.1:8000
```

其它可调参数都在 `app/config.py`，全部支持环境变量覆盖：
`CHUNK_STRATEGY`（fixed/heading/semantic）、`TOP_K`、`RERANK`（none/rrf/llm）、`MIN_SCORE`、`LLM_MODEL`。

> 索引、embedding 缓存都被 `.gitignore` 排除了，克隆下来按上面第 4 步重建即可。
> 重建 270 个片段的 embedding 大约消耗 8 万 token，按本项目实测约 0.02 元。

## 示例输出

三个真实问答的原文（含引用、SQL、耗时）在 [`examples/demo.md`](examples/demo.md)。

## 测试

不依赖模型 key 的离线单测（切分边界、BM25 排序行为），CI 在 Python 3.11 / 3.12 上跑：

```bash
python -m unittest discover -s tests -v
```

覆盖：固定切分的长度上限、标题切分不跨节、中文 bigram 分词、BM25 对稀有词的偏好、IDF 行为。

## 限制

- 语料只有 16 份文档、270 个片段，规模小，结论不一定能外推到百万级知识库。
- 只有单轮问答，没有多轮指代消解；表格类问题仍可能答不全。
- 评测集的 gold 文档是人工标的，主观性无法完全消除。
