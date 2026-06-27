"""Session 09b — Voice & Image Gen Agents: budget (Whisper+DALL-E+OAI TTS) and quality (Replicate+Flux+ElevenLabs) tracks."""
import os
from typing import TypedDict

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Budget track: no new accounts required (OpenAI + local Whisper)
BUDGET_MODEL = "claude-sonnet-4-6"
# Quality track: Replicate + ElevenLabs; no temperature on Opus 4.x
QUALITY_MODEL = "claude-opus-4-8"
MAX_TOKENS = 512


class PipelineResult(TypedDict):
    """Return type for run_pipeline — one entry per pipeline stage."""

    transcription: str
    refined_prompt: str
    image_url: str
    audio_path: str


def transcribe_budget(audio_path: str) -> str:
    """Transcribe audio locally using openai-whisper (no API key required)."""
    import whisper  # pip install openai-whisper

    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    return result["text"]


def transcribe_quality(audio_path: str) -> str:
    """Transcribe audio via Replicate-hosted Whisper large-v2."""
    import replicate  # pip install replicate; set REPLICATE_API_TOKEN

    with open(audio_path, "rb") as f:
        output = replicate.run(
            "openai/whisper:4d50797290df275329f202e48c76360b3f22b08d28c196cbc54600319435f8d2",
            input={"audio": f},
        )
    return output.get("transcription", "")


def refine_prompt(
    transcription: str,
    client: anthropic.Anthropic,
    model: str = BUDGET_MODEL,
) -> str:
    """Use Claude to turn a raw voice transcription into a polished image-gen prompt."""
    # temperature=0 only for Sonnet; Opus 4.x does not support the temperature param
    extra: dict = {} if model == QUALITY_MODEL else {"temperature": 0}
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        **extra,
        messages=[
            {
                "role": "user",
                "content": (
                    "Turn this rough voice note into a vivid, detailed image generation prompt"
                    f" (max 50 words): '{transcription}'"
                ),
            }
        ],
    )
    return response.content[0].text.strip()


def generate_image_budget(prompt: str) -> str:
    """Generate a 1024x1024 image with DALL-E 3 and return its URL."""
    import openai  # pip install openai; set OPENAI_API_KEY

    client = openai.OpenAI()
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024",
    )
    return response.data[0].url


def generate_image_quality(prompt: str) -> str:
    """Generate an image with Flux Pro via Replicate and return its URL."""
    import replicate

    output = replicate.run(
        "black-forest-labs/flux-pro",
        input={"prompt": prompt, "width": 1024, "height": 1024},
    )
    return str(output[0]) if isinstance(output, list) else str(output)


def speak_budget(text: str, output_path: str) -> str:
    """Synthesise speech with OpenAI TTS (nova voice); saves MP3 to output_path."""
    import openai

    client = openai.OpenAI()
    response = client.audio.speech.create(model="tts-1", voice="nova", input=text)
    response.stream_to_file(output_path)
    return output_path


def speak_quality(text: str, output_path: str) -> str:
    """Synthesise speech with ElevenLabs multilingual v2; saves MP3 to output_path."""
    from elevenlabs import VoiceSettings, save
    from elevenlabs.client import ElevenLabs

    el_client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    audio = el_client.text_to_speech.convert(
        text=text,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=0.75),
    )
    save(audio, output_path)
    return output_path


def run_pipeline(
    audio_path: str,
    track: str,
    client: anthropic.Anthropic,
) -> PipelineResult:
    """Run the full STT → refine → image gen → TTS pipeline for the chosen track.

    Raises ValueError for any track value other than 'budget' or 'quality'.
    """
    if track == "budget":
        transcription = transcribe_budget(audio_path)
        refined = refine_prompt(transcription, client, BUDGET_MODEL)
        image_url = generate_image_budget(refined)
        audio_out = speak_budget(refined, "output_budget.mp3")
    elif track == "quality":
        transcription = transcribe_quality(audio_path)
        refined = refine_prompt(transcription, client, QUALITY_MODEL)
        image_url = generate_image_quality(refined)
        audio_out = speak_quality(refined, "output_quality.mp3")
    else:
        raise ValueError(f"Unknown track: {track!r}. Choose 'budget' or 'quality'.")
    return PipelineResult(
        transcription=transcription,
        refined_prompt=refined,
        image_url=image_url,
        audio_path=audio_out,
    )


def main() -> None:
    """Entry point — read TRACK and AUDIO_PATH from env, then run the pipeline."""
    track = os.environ.get("TRACK", "budget")
    audio_path = os.environ.get("AUDIO_PATH", "sample.wav")
    print(f"Running {track.upper()} track. Set TRACK=quality for premium providers.")
    client = anthropic.Anthropic()
    result = run_pipeline(audio_path, track, client)
    print(f"\nTranscription : {result['transcription']}")
    print(f"Refined prompt: {result['refined_prompt']}")
    print(f"Image URL     : {result['image_url']}")
    print(f"Audio saved to: {result['audio_path']}")


if __name__ == "__main__":
    main()
