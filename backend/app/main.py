import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import agent, db, voice
from .llm import PROVIDERS
from .seller_data import SELLER, seller_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kam")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.connect()
    yield


app = FastAPI(title="Snapdeal Virtual KAM", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def public_state(session: dict) -> dict:
    return {k: v for k, v in session.items() if k not in ("prior", "_id")}


def get_session(session_id: str) -> dict:
    session = agent.SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@app.get("/api/health")
async def health():
    return {"ok": True, "llm_providers": [p.label for p in PROVIDERS], "mongo": db.enabled()}


@app.get("/api/seller")
async def seller():
    return seller_context()


@app.get("/api/history")
async def history():
    return await db.list_sessions(SELLER["seller_id"])


@app.delete("/api/history")
async def clear_history():
    return {"deleted": await db.clear_sessions(SELLER["seller_id"])}


@app.post("/api/session")
async def start_session():
    prior = await db.last_completed_session(SELLER["seller_id"])
    session = agent.new_session(prior)
    greeting = session["transcript"][0]["text"]
    audio = await voice.synthesize(greeting)
    await db.save_session(session)
    return {"reply": greeting, "audio": audio, "state": public_state(session)}


@app.post("/api/session/{session_id}/turn")
async def turn(session_id: str, audio: UploadFile | None = File(None), text: str | None = Form(None)):
    session = get_session(session_id)
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    if audio is not None:
        user_text = await voice.transcribe(await audio.read(), audio.filename or "speech.wav")
        timings["stt"] = round(time.perf_counter() - t0, 2)
    else:
        user_text = (text or "").strip()

    if not user_text:
        reply = "Sorry, I didn't catch that. Could you please say it again?"
        return {"transcript": "", "reply": reply, "audio": await voice.synthesize(reply),
                "end_call": False, "state": public_state(session), "timings": timings}

    t1 = time.perf_counter()
    result = await agent.take_turn(session, user_text)
    timings["llm"] = round(time.perf_counter() - t1, 2)

    if result["end_call"]:
        summary = await agent.summarize(session)
        if summary.get("spoken_summary"):
            result["reply"] = summary["spoken_summary"]
            session["transcript"][-1]["text"] = result["reply"]

    t2 = time.perf_counter()
    audio_b64 = await voice.synthesize(result["reply"])
    timings["tts"] = round(time.perf_counter() - t2, 2)

    await db.save_session(session)
    log.info("turn %s timings=%s", session_id, timings)
    return {"transcript": user_text, "reply": result["reply"], "audio": audio_b64,
            "end_call": result["end_call"], "state": public_state(session), "timings": timings}


@app.post("/api/session/{session_id}/end")
async def end_session(session_id: str):
    """Seller hung up manually: build the case-file summary and speak the recap."""
    session = get_session(session_id)
    if not session["summary"]:
        await agent.summarize(session)
    spoken = session["summary"].get("spoken_summary") or "Thank you for your time. Goodbye!"
    session["transcript"].append({"role": "assistant", "text": spoken, "ts": agent._now()})
    audio = await voice.synthesize(spoken)
    await db.save_session(session)
    return {"reply": spoken, "audio": audio, "state": public_state(session)}
