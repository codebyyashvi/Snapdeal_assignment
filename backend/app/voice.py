import base64
import re

import httpx

from . import config

_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0))
_headers = {"X-API-Key-ID": config.GNANI_API_KEY}


async def transcribe(audio: bytes, filename: str = "speech.wav") -> str:
    """Gnani Prisma STT (REST, clips up to 30 s)."""
    r = await _client.post(
        f"{config.GNANI_BASE_URL}/stt/v3",
        headers=_headers,
        files={"audio_file": (filename, audio, "audio/wav")},
        data={"model": config.GNANI_STT_MODEL, "language_code": config.GNANI_STT_LANGUAGE},
    )
    r.raise_for_status()
    return (r.json().get("transcript") or "").strip()


def speakable(text: str) -> str:
    """TTS reads symbols literally, so strip markdown and spell out currency."""
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"(^|\s)\(?\d\)\s*", r"\1", text)
    text = re.sub(r"[*_#`>\[\]]", "", text)
    text = re.sub(r"(?:₹|\bRs\.?|\bINR)\s?([\d,]+)", r"\1 rupees", text)
    text = text.replace("%", " percent")
    return re.sub(r"\s+", " ", text).strip()


async def synthesize(text: str) -> str:
    """Gnani Timbre TTS (REST). Returns base64 WAV."""
    r = await _client.post(
        f"{config.GNANI_BASE_URL}/api/v1/tts/inference",
        headers=_headers,
        json={
            "text": speakable(text),
            "voice": config.GNANI_TTS_VOICE,
            "model": config.GNANI_TTS_MODEL,
            "language": config.GNANI_TTS_LANGUAGE,
            "speed": 1.05,
            "audio_config": {
                "sample_rate": 22050,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        },
    )
    r.raise_for_status()
    return base64.b64encode(r.content).decode()
