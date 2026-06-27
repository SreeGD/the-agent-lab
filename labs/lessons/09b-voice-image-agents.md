# Session 09b — Voice & Image Generation Agents

**Track D — Data & Multi-modal | Week 4, Saturday | 2 hours**

**Prerequisites:** Session 09 (Files & Document AI)

---

## Why This Matters

Voice is the most natural human interface.  Image generation is the fastest
prototyping tool for visual ideas.  Combining them with a reasoning layer
turns a rough spoken thought into a polished visual artifact — without the
user ever touching a keyboard.

This session builds that pipeline in two flavors:

- **Budget track** — local Whisper + OpenAI DALL-E 3 + OpenAI TTS.  No new
  accounts beyond what the course already uses.
- **Quality track** — Replicate Whisper + Flux Pro + ElevenLabs.  Noticeably
  better output; requires two extra API keys.

---

## 1. Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: audio file (.wav / .mp3)                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │    STT — Transcribe    │
            │                        │
            │  budget: local Whisper │
            │  quality: Replicate    │
            └────────────┬───────────┘
                         │ raw text
                         ▼
            ┌────────────────────────┐
            │  Reasoning — Claude    │
            │                        │
            │  refine_prompt()       │
            │  budget : sonnet-4-6   │
            │  quality: opus-4-8     │
            └────────────┬───────────┘
                         │ polished prompt (≤50 words)
                  ┌──────┴───────┐
                  ▼              ▼
     ┌────────────────┐  ┌───────────────────┐
     │  Image Gen     │  │   TTS — Speak     │
     │                │  │                   │
     │ budget:DALL-E3 │  │ budget: OAI TTS   │
     │ quality:Flux   │  │ quality:ElevenLabs│
     └───────┬────────┘  └────────┬──────────┘
             │                    │
             ▼                    ▼
         image URL           audio file (.mp3)
              └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │  PipelineResult  │
               │  TypedDict       │
               └──────────────────┘
```

Claude sits between the raw transcription and the downstream generators.
It converts imprecise speech ("paint me something pretty with mountains")
into a precise, detail-rich prompt that image models respond well to.

---

## 2. Budget vs Quality Track

| Dimension | Budget | Quality |
|---|---|---|
| STT | openai-whisper local (base model) | Replicate Whisper large-v2 |
| Reasoning | claude-sonnet-4-6 | claude-opus-4-8 |
| Image gen | DALL-E 3 (OpenAI) | Flux Pro (Replicate) |
| TTS | OpenAI TTS nova | ElevenLabs multilingual v2 |
| New accounts needed | None (OpenAI already in use) | Replicate + ElevenLabs |
| Approx cost per run | ~$0.05 | ~$0.20 |
| Latency | 5–15 s (whisper CPU) | 15–30 s (Replicate cold start) |
| Image quality | Good | Excellent |
| Voice naturalness | Good | Highly natural |
| Best for | Rapid prototyping, no new setup | Demos, client presentations |

---

## 3. Provider Trade-Off Matrix

### Speech-to-Text

| Provider | Speed | Accuracy | Cost | Privacy |
|---|---|---|---|---|
| Whisper base (local) | Slow on CPU | Good | Free | Data stays on device |
| Whisper large-v2 (Replicate) | Fast | Excellent | ~$0.001/min | Leaves device |
| OpenAI Whisper API | Fast | Excellent | $0.006/min | Leaves device |

**Choose local Whisper when:** regulated data; no internet; cost matters.
**Choose Replicate when:** better accuracy with minimal setup overhead.

### Image Generation

| Provider | Quality | Style control | Cost | Latency |
|---|---|---|---|---|
| DALL-E 3 | High | Good via prompt | $0.04/image | 5–10 s |
| Flux Pro | Excellent | Excellent via prompt | ~$0.05/image | 10–20 s |
| Stable Diffusion (self-hosted) | Variable | Full LoRA control | GPU cost | <1 s (GPU) |

**Choose DALL-E 3 when:** you need reliable moderation + simple prompt.
**Choose Flux Pro when:** photorealistic quality and aesthetic control matter.

### Text-to-Speech

| Provider | Naturalness | Voices | Cost | Latency |
|---|---|---|---|---|
| OpenAI TTS (tts-1) | Good | 6 built-in | $0.015/1K chars | <2 s |
| ElevenLabs v2 | Excellent | 100s + cloning | $0.002/1K chars | 2–5 s |
| Edge TTS (local) | Acceptable | Many locales | Free | <1 s |

**Choose OpenAI TTS when:** quick integration with no extra account.
**Choose ElevenLabs when:** voice cloning or multi-lingual naturalness is needed.

---

## 4. Code Walk-Through

### TypedDict return contract

```python
class PipelineResult(TypedDict):
    transcription: str
    refined_prompt: str
    image_url: str
    audio_path: str
```

TypedDict enforces the shape at type-check time without runtime overhead.
Callers can unpack keys like a regular dict.

### Local imports for optional dependencies

```python
def transcribe_budget(audio_path: str) -> str:
    import whisper  # deferred — only loaded when this function runs
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]
```

Placing `import whisper` inside the function means the module loads fine
even when `openai-whisper` is not installed — the import error only fires
when the function is actually called.  This pattern keeps dependencies
optional and makes the quality track functions completely independent.

### Claude as reasoning layer

```python
def refine_prompt(
    transcription: str,
    client: anthropic.Anthropic,
    model: str = BUDGET_MODEL,
) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": (
                "Turn this rough voice note into a vivid, detailed image generation prompt"
                f" (max 50 words): '{transcription}'"
            ),
        }],
    )
    return response.content[0].text.strip()
```

Key design points:
- `max_tokens` is always explicit — never rely on the API default.
- `claude-opus-4-8` is passed for the quality track; Opus 4.x does not
  accept a `temperature` parameter.
- The prompt constrains output length (50 words) to keep image-model
  prompts tight and coherent.

### run_pipeline selects providers by track

```python
def run_pipeline(audio_path, track, client):
    if track == "budget":
        transcription = transcribe_budget(audio_path)
        refined = refine_prompt(transcription, client, BUDGET_MODEL)
        image_url = generate_image_budget(refined)
        audio_out = speak_budget(refined, "output_budget.mp3")
    elif track == "quality":
        ...
    else:
        raise ValueError(f"Unknown track: {track!r}. Choose 'budget' or 'quality'.")
    return PipelineResult(...)
```

The `ValueError` guard at the end is a guard clause — it fails fast with a
clear message instead of silently returning an empty result.

---

## 5. Run It

### Budget track (no new accounts)

```bash
export OPENAI_API_KEY=sk-...
export AUDIO_PATH=path/to/your.wav   # any short voice clip works
export TRACK=budget
python labs/09b_voice_image_agents.py
```

Output:
```
Running BUDGET track. Set TRACK=quality for premium providers.

Transcription : paint me a sunset over the ocean with warm colors
Refined prompt: A breathtaking sunset over a calm ocean, sky ablaze with
                gold and amber hues, gentle waves reflecting crimson light,
                silhouetted palm trees on the horizon, cinematic composition.
Image URL     : https://oaidalleapiprodscus.blob.core.windows.net/...
Audio saved to: output_budget.mp3
```

### Quality track (Replicate + ElevenLabs)

```bash
export OPENAI_API_KEY=sk-...           # still needed for Anthropic → OpenAI key
export ANTHROPIC_API_KEY=sk-ant-...
export REPLICATE_API_TOKEN=r8_...
export ELEVENLABS_API_KEY=...
export AUDIO_PATH=path/to/your.wav
export TRACK=quality
python labs/09b_voice_image_agents.py
```

### Install dependencies

```bash
# Budget track
pip install openai-whisper openai anthropic python-dotenv

# Quality track additions
pip install replicate elevenlabs
```

### Run unit tests

```bash
pytest tests/unit/test_09b_voice_image_agents.py -v
```

---

## 6. Extension Ideas

1. **Real-time loop** — record a 5-second clip, run the pipeline, display the
   image, speak the refined prompt — repeat every 10 seconds.
2. **Streamlit UI** — add a mic button (streamlit-audio-recorder), show
   pipeline stages in real time via `st.status`.
3. **Multi-language** — set the Whisper `language` parameter and use
   ElevenLabs' multilingual model to output TTS in the same language.
4. **Prompt history** — store `PipelineResult` dicts in SQLite; let the
   user browse previous runs and regenerate images from saved prompts.

---

## Key Takeaways

1. **Claude is the semantic bridge** — raw speech is ambiguous; Claude
   translates intent into the precise vocabulary that image models need.
2. **Defer optional imports** — place `import whisper` / `import replicate`
   inside functions so the module is usable without every dependency installed.
3. **TypedDict enforces contracts** — gives mypy and IDEs full type coverage
   with zero runtime cost.
4. **Opus 4.x has no temperature** — never pass `temperature` to
   `claude-opus-4-8`; always set `max_tokens` explicitly on every model.
5. **TRACK env var = zero-code switching** — the same pipeline code drives
   two completely different provider stacks by reading one variable.

---

## Further Reading

- [openai-whisper on GitHub](https://github.com/openai/whisper)
- [DALL-E 3 API docs](https://platform.openai.com/docs/guides/images)
- [Flux Pro on Replicate](https://replicate.com/black-forest-labs/flux-pro)
- [OpenAI TTS docs](https://platform.openai.com/docs/guides/text-to-speech)
- [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python)
- [Replicate Python client](https://github.com/replicate/replicate-python)
