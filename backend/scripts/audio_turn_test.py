"""End-to-end audio test: synthesize a seller utterance, send it as WAV through /turn."""
import asyncio
import base64

import httpx

from app import voice

API = "http://127.0.0.1:8000/api"


async def main():
    seller_wav = base64.b64decode(await voice.synthesize(
        "My sales have dropped significantly this month. I don't understand why. Can you help me?"))
    async with httpx.AsyncClient(timeout=90) as c:
        s = (await c.post(f"{API}/session")).json()
        r = (await c.post(f"{API}/session/{s['state']['id']}/turn",
                          files={"audio": ("speech.wav", seller_wav, "audio/wav")})).json()
        print("heard:", r["transcript"])
        print("reply:", r["reply"])
        print("timings:", r["timings"], "audio bytes:", len(base64.b64decode(r["audio"])))


asyncio.run(main())
