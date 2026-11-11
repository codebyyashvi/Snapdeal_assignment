# Snapdeal Virtual KAM - AI voice account manager

A browser-based, hands-free voice bot that a Snapdeal seller can "call" when sales drop. It diagnoses the account before the call starts, confirms the root cause by talking to the seller, agrees a dated action plan (with tasks the KAM owns), books a follow-up, and remembers it all for the next call.

## Run locally

Requirements: Python 3.11+, Node 20+.

```powershell
# Backend (FastAPI) - http://127.0.0.1:8000
cd backend
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # fill in keys
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# Frontend (React + Vite + Tailwind) - http://localhost:5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in Chrome or Edge, click **Call Virtual KAM**, allow the microphone, and talk. There is no push-to-talk: the bot detects when you stop speaking.

Use **Clear memory** (bottom of the right panel) to reset to a first-time caller before recording a demo.

## Layout

```
backend/app/
  main.py         FastAPI routes: /api/session, /turn (audio or text), /end, /seller, /history
  agent.py        System prompt, conversation playbook, per-turn state machine, summary
  seller_data.py  Mock data (from the brief + flagged assumptions) and the rule-based diagnosis
  llm.py          Provider-agnostic LLM client with fallback chain (Groq -> Azure -> OpenAI)
  voice.py        Gnani Vachana STT (Prisma v3.0) and TTS (Timbre v2.5)
  db.py           MongoDB persistence for sessions / case files (optional)
backend/scripts/
  simulate_call.py    Full scripted call in text mode (prints stage, plan, summary)
  audio_turn_test.py  Real audio round trip: TTS -> WAV -> /turn -> STT -> LLM -> TTS
frontend/src/
  lib/voice.js    Mic capture, voice-activity detection, 16 kHz WAV encoder, playback
  App.jsx         Call loop (listen -> think -> speak -> listen)
  components/     CallPanel (orb, transcript, stage tracker), Workspace (live KAM dashboard)
```

See `SUBMISSION_NOTE.md` for the models, voice stack, workflow and design decisions.
