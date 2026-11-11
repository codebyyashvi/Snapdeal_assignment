import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


GNANI_API_KEY = env("GNANI_API_KEY")
GNANI_BASE_URL = env("GNANI_BASE_URL", "https://api.vachana.ai").rstrip("/")
GNANI_STT_MODEL = env("GNANI_STT_MODEL", "prisma-v3.0")
GNANI_STT_LANGUAGE = env("GNANI_STT_LANGUAGE", "en-IN")
GNANI_TTS_VOICE = env("GNANI_TTS_VOICE", "Nalini")
GNANI_TTS_MODEL = env("GNANI_TTS_MODEL", "timbre-v2.5")
GNANI_TTS_LANGUAGE = env("GNANI_TTS_LANGUAGE", "en-IN")

LLM_PROVIDER = env("LLM_PROVIDER", "auto").lower()
GROQ_API_KEY = env("GROQ_API_KEY")
GROQ_MODEL = env("GROQ_MODEL", "qwen/qwen3.8-27b")
# Each Groq model has its own tokens-per-minute quota, so fallbacks also absorb rate limits.
GROQ_FALLBACK_MODELS = [m.strip() for m in env("GROQ_FALLBACK_MODELS", "openai/gpt-oss-120b,openai/gpt-oss-20b").split(",") if m.strip()]
AZURE_DEPLOYMENT = env("OPEN_AI_DEPLOYMENT_NAME")
AZURE_ENDPOINT = env("OPEN_AI_ENDPOINT")
AZURE_KEY = env("OPEN_AI_KEY")
AZURE_API_VERSION = env("OPEN_AI_API_VERSION", "2024-02-15-preview")
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")

MONGO_URI = env("MONGO_URI")
MONGO_DB = env("MONGO_DB", "snapdeal_kam")
