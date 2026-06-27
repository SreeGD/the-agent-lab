# Session 07b — Open-Weight Models & HuggingFace Ecosystem

**Track C — Alt Architectures | Week 3 | 2 hours**

Prerequisites: Session 07 (Anthropic SDK / Claude Agent SDK)

---

## Learning Objectives

By the end of this session you will be able to:

1. Navigate HuggingFace Hub to find, filter, and evaluate models programmatically.
2. Name the major open-weight model families and explain the key architectural choices that differentiate them.
3. Extract the essential information from an arXiv model-card paper in under 10 minutes.
4. Read benchmark leaderboards critically — knowing what each benchmark measures and what it doesn't.
5. Wire up a provider-agnostic shootout using LiteLLM to compare outputs and latency across models.

---

## 1. HuggingFace Hub Anatomy

HuggingFace Hub is the central registry for open-weight models, datasets, and Spaces (demo apps). Understanding its structure lets you find the right model without scrolling endlessly.

### 1.1 URL Structure

```
https://huggingface.co/{org}/{repo}
                        └── e.g. meta-llama/Llama-3-70B-Instruct
```

Every model page has four tabs that matter:

| Tab | What to look for |
|-----|-----------------|
| **Model card** | Architecture, training data, license, intended use |
| **Files & versions** | `config.json` (architecture), `tokenizer_config.json`, safetensors shards |
| **Community** | Issues, discussions — surfaced fine-tune failures and inference quirks |
| **Spaces** | Hosted demos — fastest way to try before you download |

### 1.2 Pipeline Tags (the primary filter)

HuggingFace organises models by `pipeline_tag`. The tags you'll encounter most often:

| Tag | Use case |
|-----|----------|
| `text-generation` | Chat, completion, coding |
| `text2text-generation` | Seq2seq (T5-family, summarisation) |
| `sentence-similarity` | Embedding / RAG retrieval |
| `image-text-to-text` | Vision-language (LLaVA, Phi-3-Vision) |
| `automatic-speech-recognition` | Whisper family |

### 1.3 HfApi — Programmatic Access

```python
from huggingface_hub import HfApi

api = HfApi()

# List top text-generation models by download count
models = api.list_models(
    filter="text-generation",
    sort="downloads",
    direction=-1,   # descending
    limit=10,
)

for m in models:
    print(m.modelId, m.downloads)
```

Key `list_models` parameters:

| Parameter | Type | Notes |
|-----------|------|-------|
| `filter` | `str` | Pipeline tag or arbitrary tag |
| `sort` | `str` | `"downloads"`, `"likes"`, `"lastModified"` |
| `direction` | `int` | `-1` = descending |
| `limit` | `int` | Max results (default 100) |
| `search` | `str` | Free-text search over model names |

### 1.4 Model Object Fields

A model returned by `list_models` exposes:

```python
m.modelId        # "meta-llama/Llama-3-70B-Instruct"
m.downloads      # int — last-30-day download count
m.tags           # list[str] — pipeline tag + library tags + custom
m.likes          # int
m.lastModified   # datetime
```

---

## 2. Open-Weight Model Families

"Open-weight" means the model weights are publicly available, usually under a custom license. "Open-source" additionally requires the training code and data — most models are only open-weight.

### 2.1 Family Comparison Table

| Family | Lead org | Flagship model (2025) | Params (flagship) | Context | License | Strengths |
|--------|----------|-----------------------|-------------------|---------|---------|-----------|
| **Llama** | Meta | Llama 3.3 70B Instruct | 70B | 128 K | Llama 3 Community | Coding, instruction-following, widest ecosystem |
| **Qwen** | Alibaba | Qwen2.5-72B-Instruct | 72B | 128 K | Apache 2.0 | Multilingual (Chinese), math, long-context |
| **DeepSeek** | DeepSeek AI | DeepSeek-V3 | 671B MoE | 64 K | DeepSeek | Coding, benchmarks competitive with GPT-4o |
| **Mistral** | Mistral AI | Mistral-Large-2 | 123B | 128 K | MRL (commercial OK) | Efficient, strong function-calling |
| **Phi** | Microsoft | Phi-3.5-MoE-instruct | 16B MoE | 128 K | MIT | Small but capable; edge / mobile deployment |
| **Gemma** | Google | Gemma 2 27B | 27B | 8 K | Gemma TOS | Research-friendly, safety-tuned |
| **Command R** | Cohere | Command R+ | 104B | 128 K | CC-BY-NC | RAG-optimised, citation generation |

### 2.2 MoE vs Dense

Most frontier open models now use **Mixture of Experts (MoE)**:

- A MoE model has many more total parameters than it uses per token.
- A router selects a subset of "expert" FFN layers for each token (typically 2 of N).
- **Effect**: higher quality per compute dollar, but heavier VRAM at serving time.
- DeepSeek-V3: 671B total, ~37B active per token.

### 2.3 Licensing Quick Reference

| License | Commercial use | Redistribution | Fine-tune & release |
|---------|---------------|----------------|---------------------|
| Apache 2.0 | ✓ | ✓ | ✓ |
| MIT | ✓ | ✓ | ✓ |
| Llama 3 Community | ✓ (<700M MAU) | ✓ | ✓ (must credit Meta) |
| Mistral Research (MRL) | ✓ | ✓ | ✓ |
| DeepSeek | ✓ | Restricted | Check terms |
| Gemma TOS | Research OK | Restricted | Restricted |

Always check the model card — licenses can change between versions.

---

## 3. Reading an arXiv Paper in 10 Minutes

Model papers are long. The 3-pass workflow below extracts 80% of the value in 10 minutes.

### Pass 1 — Title + Abstract (2 min)

Answer these questions from the abstract alone:

1. What problem does this model solve?
2. What is the architectural novelty (if any)?
3. What benchmarks do they lead on?

If the abstract doesn't answer all three, this paper is likely incremental.

### Pass 2 — Architecture + Training Data sections (5 min)

Look for:

- **Architecture diagram** — decoder-only, encoder-decoder, MoE, SSM?
- **Parameter count** — total vs active (for MoE)
- **Context length** — hard limit vs practical limit
- **Training tokens** — how much data?
- **Post-training** — SFT? RLHF? DPO? Constitutional AI?
- **Training data** — web crawl, code, math, multilingual ratio?

### Pass 3 — Results table (3 min)

- Compare on the benchmarks you care about (see Section 4).
- Check the **baseline comparisons** — are they cherry-picking weak baselines?
- Look for **ablations** — do they show which design choice actually helped?
- Scan the **limitations** section — honest papers have one.

### arXiv Search Tips

```python
# Search arXiv via the API (no auth needed)
# Use defusedxml — stdlib xml.etree.ElementTree is vulnerable to XXE attacks
import urllib.request
import urllib.parse
import defusedxml.ElementTree as ET

query = urllib.parse.quote("ti:Llama AND abs:instruction tuning")
url = f"http://export.arxiv.org/api/query?search_query={query}&max_results=5"
with urllib.request.urlopen(url) as r:
    tree = ET.parse(r)

ns = {"atom": "http://www.w3.org/2005/Atom"}
for entry in tree.findall("atom:entry", ns):
    title = entry.find("atom:title", ns).text.strip()
    link  = entry.find("atom:id", ns).text.strip()
    print(title, "→", link)
```

---

## 4. Benchmark Explainer

Benchmarks are **proxies**, not ground truth. Know what each one actually measures.

### 4.1 MMLU — Massive Multitask Language Understanding

- **What**: 57 academic subjects (law, medicine, history, math, CS…) as 4-choice MCQs.
- **Measures**: Breadth of world knowledge and reasoning.
- **Ceiling effect**: Top models cluster between 85–90; differences < 2 points are noise.
- **Does NOT measure**: Long-form generation quality, instruction-following, coding.
- **Typical scores** (2025): GPT-4o 87.2, DeepSeek-V3 88.5, Llama-3-70B 82.0.

### 4.2 HumanEval

- **What**: 164 Python programming problems authored by OpenAI.
- **Measures**: Pass@1 — does the model's first attempt pass all unit tests?
- **Commonly inflated**: Many models have seen HumanEval in training data. Use HumanEval+ or LiveCodeBench for a fresher signal.
- **Typical scores**: GPT-4o 90.2, DeepSeek-V3 89.1, Llama-3-70B 72.4.

### 4.3 LMSYS Chatbot Arena

- **What**: Anonymous pairwise human preference voting at chat.lmsys.org.
- **Measures**: Real user preference — style, helpfulness, safety, creativity.
- **Strengths**: Hard to game (humans rate blind), ecologically valid.
- **Weaknesses**: Slower to update; biased toward verbose/confident answers.
- **Score**: Elo-style rank. Higher rank = better. Rank 1 is the best on the leaderboard.

### 4.4 MTEB — Massive Text Embedding Benchmark

- **What**: 56 tasks across 8 embedding task categories (retrieval, clustering, classification…).
- **Measures**: Quality of text embeddings for downstream NLP tasks.
- **Use case**: Pick this benchmark when choosing an embedding model for RAG.
- **Typical scores**: OpenAI text-embedding-3-large 64.6, Cohere Embed v3 63.0.

### 4.5 Benchmark Selection Heuristic

```
IF task is knowledge-intensive QA       → look at MMLU
IF task is code generation              → look at HumanEval (prefer LiveCodeBench)
IF task is chat / general assistant     → look at LMSYS Chatbot Arena rank
IF task is RAG / semantic search        → look at MTEB
IF task is instruction-following        → look at IFEval
IF task is long-context                 → look at RULER or LongBench
```

### 4.6 What Benchmarks Miss

- **Latency and cost** — a model scoring 2 points higher on MMLU but costing 10x more is rarely worth it.
- **Your specific domain** — always run a small eval on your own data before committing.
- **Prompt sensitivity** — results can shift ±5 points with rephrasing.
- **Safety and refusal rate** — no standard benchmark captures this well.

---

## 5. Provider Shootout with LiteLLM

LiteLLM provides a unified OpenAI-compatible interface to 100+ models. Use it to run controlled experiments.

```python
import time
import litellm

def provider_shootout(prompt: str, providers: list[str]) -> list[dict]:
    results = []
    for provider in providers:
        start = time.monotonic()
        response = litellm.completion(
            model=provider,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=256,
        )
        latency_ms = (time.monotonic() - start) * 1000
        output = response.choices[0].message.content or ""
        results.append({"provider": provider, "output": output, "latency_ms": latency_ms})
    return results
```

### LiteLLM Model String Format

```
{provider}/{model_name}
```

Examples:

| Provider | Model string |
|----------|-------------|
| Anthropic | `anthropic/claude-sonnet-4-6` |
| OpenAI | `openai/gpt-4o-mini` |
| Together AI | `together_ai/meta-llama/Llama-3-70b-chat-hf` |
| Groq | `groq/llama3-70b-8192` |
| HuggingFace TGI | `huggingface/mistralai/Mistral-7B-Instruct-v0.2` |

### Environment Variables Required

```bash
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
TOGETHER_AI_API_KEY=...    # optional
GROQ_API_KEY=...           # optional
```

---

## 6. Lab — `07b_ecosystem_fluency.py`

The lab file exercises all three skills in sequence:

1. **HF Hub search** — `search_hf_models(task, limit)` calls `HfApi.list_models` and returns a clean list.
2. **Benchmark lookup** — `benchmark_scores(model_name, reference)` queries the static `BENCHMARK_REFERENCE` table.
3. **Provider shootout** — `provider_shootout(prompt, providers)` calls each LiteLLM provider and records latency.

### Running the lab

```bash
cd /Users/srmallip/projects/AgenticCourse
python labs/07b_ecosystem_fluency.py
```

Expected output (truncated):

```
================================================================
1. HUGGINGFACE HUB — TOP TEXT-GENERATION MODELS
================================================================
  meta-llama/Llama-3.3-70B-Instruct             45,123,456 downloads
  ...

================================================================
2. PROVIDER SHOOTOUT
================================================================
  anthropic/claude-sonnet-4-6 (823ms):
  'Gradient descent iteratively adjusts model parameters ...'
  ...

================================================================
3. BENCHMARK SCORES
================================================================
Model                      MMLU  HumanEval   LMSYS   MTEB
----------------------------------------------------------
gpt-4o                     87.2       90.2       3   64.6
claude-opus-4-7            88.2       84.9       2   62.1
...
```

### Running the tests

```bash
pytest tests/unit/test_07b_ecosystem_fluency.py -v
```

All four tests mock network calls, so no API keys are required.

---

## 7. Key Takeaways

1. **HuggingFace Hub** is the npm of ML — `HfApi.list_models` is your package search.
2. **Open-weight ≠ open-source** — always check the license before deploying commercially.
3. **MoE models** are parameter-efficient at inference but VRAM-heavy; pick dense models for memory-constrained deployments.
4. **arXiv 3-pass** (abstract → architecture → results) gives you 80% of the value in 10 minutes.
5. **No benchmark is universal** — match the benchmark to your task; always validate on your own data.
6. **LiteLLM** is the LangChain-free way to run multi-provider experiments with a single unified API.

---

## Further Reading

- HuggingFace Hub Docs: https://huggingface.co/docs/hub
- LiteLLM Docs: https://docs.litellm.ai
- LMSYS Chatbot Arena: https://chat.lmsys.org
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- MMLU Paper: https://arxiv.org/abs/2009.03300
- HumanEval Paper: https://arxiv.org/abs/2107.03374
- Llama 3 Paper: https://arxiv.org/abs/2407.21783
- DeepSeek-V3 Paper: https://arxiv.org/abs/2412.19437
