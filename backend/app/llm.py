import json
import logging
import re
from dataclasses import dataclass, field

from openai import AsyncAzureOpenAI, AsyncOpenAI

from . import config

log = logging.getLogger("kam.llm")


@dataclass
class Provider:
    name: str
    client: AsyncOpenAI
    model: str
    extra: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}"


def _groq_extra(model: str) -> dict:
    # Groq's strict JSON mode rejects Qwen output; the prompt alone yields clean JSON.
    if model.startswith("openai/gpt-oss"):
        return {"response_format": {"type": "json_object"}, "extra_body": {"reasoning_effort": "low"}}
    return {}


def _providers() -> list[Provider]:
    by_name: dict[str, list[Provider]] = {}
    if config.GROQ_API_KEY:
        groq = AsyncOpenAI(api_key=config.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1",
                           timeout=12, max_retries=0)
        models = [config.GROQ_MODEL, *[m for m in config.GROQ_FALLBACK_MODELS if m != config.GROQ_MODEL]]
        by_name["groq"] = [Provider("groq", groq, m, _groq_extra(m)) for m in models]
    if config.AZURE_KEY and config.AZURE_ENDPOINT:
        azure = AsyncAzureOpenAI(api_key=config.AZURE_KEY, azure_endpoint=config.AZURE_ENDPOINT,
                                 api_version=config.AZURE_API_VERSION, timeout=12, max_retries=0)
        by_name["azure"] = [Provider("azure", azure, config.AZURE_DEPLOYMENT, {"response_format": {"type": "json_object"}})]
    if config.OPENAI_API_KEY:
        openai = AsyncOpenAI(api_key=config.OPENAI_API_KEY, timeout=12, max_retries=0)
        by_name["openai"] = [Provider("openai", openai, config.OPENAI_MODEL, {"response_format": {"type": "json_object"}})]

    order = ["groq", "azure", "openai"]
    if config.LLM_PROVIDER in by_name:
        order.remove(config.LLM_PROVIDER)
        order.insert(0, config.LLM_PROVIDER)
    return [p for name in order for p in by_name.get(name, [])]


PROVIDERS = _providers()


def _parse_json(raw: str, text_key: str | None) -> dict:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        if text_key and raw and "{" not in raw:
            log.info("LLM returned plain text; using it as %s", text_key)
            return {text_key: raw}
        raise


async def chat_json(
    messages: list[dict], max_tokens: int = 700, temperature: float = 0.4, text_key: str | None = None
) -> tuple[dict, str]:
    """Try each configured provider/model in order; return (parsed JSON, provider label).

    If the model answers in plain prose and text_key is set, the prose is returned under that key.
    """
    last_error: Exception | None = None
    for p in PROVIDERS:
        for attempt in range(2):
            try:
                resp = await p.client.chat.completions.create(
                    model=p.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens + (800 if "gpt-oss" in p.model else 0),
                    **p.extra,
                )
                return _parse_json(resp.choices[0].message.content or "", text_key), p.label
            except Exception as e:  # noqa: BLE001 - retry parse failures once, then next provider
                log.warning("LLM %s failed: %s", p.label, str(e)[:300])
                last_error = e
                if not isinstance(e, (json.JSONDecodeError, ValueError)):
                    break
    raise RuntimeError(f"All LLM providers failed: {last_error}")
