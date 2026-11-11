# Snapdeal Virtual KAM - submission note

## The idea
Most "AI assistants" wait for questions. A good KAM doesn't: they look at the account *before* the call, already know what is wrong, use the call to confirm *why*, and hang up with owners, dates and a follow-up. This bot is built around that loop: **diagnose → confirm → plan → commit → follow up → remember**.

## Workflow
1. **Pre-call diagnosis (deterministic, no LLM).** `seller_data.diagnose()` decomposes the drop: Sales = Orders × ASP. ASP is flat at ₹500, so the whole ₹65,000 (32.5%) fall comes from 130 fewer orders, and pricing is ruled out. It then ranks causes by rupee impact: 6 best-sellers out of stock (~₹44k/month), cancellations up from 8% to 14% (21 of 38 were stock-outs and 9 were late dispatch), and search visibility down 32% as a knock-on effect. Putting the numbers in code means the LLM cannot invent them.
2. **Voice call.** The browser captures the microphone and detects speech locally (adaptive noise floor). After about 1.1 s of silence it sends a 16 kHz WAV to the FastAPI backend. The backend runs **STT, then the LLM, then TTS** and returns the reply audio, then the bot starts listening again. There is no push-to-talk, and interrupting the bot (barge-in) is optional.
3. **Agent turn.** The LLM gets a compact fact sheet, the diagnosis, the transcript and the current call state. It returns JSON: the spoken `reply`, the conversation `stage`, `seller_facts` learned, `confirmed_issues`, the full `action_plan` (owner seller/KAM, due date, impact, proposed/agreed) and a `follow_up`. The UI shows these live, so the seller (and the reviewer) can watch the case file fill in.
4. **Playbook stages:** discovery → diagnosis (1–2 follow-ups that change the advice, e.g. why stock ran out, why dispatch slowed) → 2–3 recommendations with rupee impact → commitment (dates, plus tasks the KAM itself takes on, such as sale nomination and ad credit) → closing.
5. **Close and memory.** At the end, a summary call produces key issues, recommendations and next steps, and the bot speaks a recap. The session is saved to MongoDB. On the next call the KAM opens with *"Last time you agreed to restock your top six items. How is that going?"*

## Models and voice technology
| Layer | Choice | Why |
|---|---|---|
| Speech-to-text | **Gnani Vachana Prisma v3.0** (REST, `en-IN`) | Built for Indian accents and Hinglish; ~1.2–1.6 s per utterance |
| Text-to-speech | **Gnani Vachana Timbre v2.5**, voice *Nalini* (`en-IN`) | Natural Indian-English voice; ~1.5–2 s per reply |
| LLM | **Groq `qwen/qwen3.8-27b`**, falling back to Groq `gpt-oss-120b` / `gpt-oss-20b`, then Azure OpenAI / OpenAI `gpt-4o-mini` | Groq gives ~0.5–1.5 s responses for voice. Each Groq model has its own rate limit, so the fallback chain also absorbs the free-tier 7k tokens/min limit |
| Backend / DB | Python FastAPI, MongoDB (optional, runs in-memory without it) | |
| Frontend | React + Vite + Tailwind, Web Audio API | |

Typical end-to-end turn: **about 4 s** (STT 1.5 s, LLM 1 s, TTS 1.6 s). Per-turn timings are shown under each reply in the UI.

## Decisions and trade-offs
- **Numbers in code, words from the LLM.** Rule-based diagnosis handles the facts; the LLM handles empathy, questioning and tailoring the advice to what the seller says (supplier delay vs cash flow vs staff shortage).
- **Voice-specific prompting.** Replies under 50 words, one question at a time, Indian number style ("1 lakh 35 thousand rupees"), and no symbols or abbreviations. A sanitiser cleans up anything that slips through before TTS.
- **Robust JSON.** The whole call is sent as one user message, because when past turns were sent as plain assistant messages the model copied that style and stopped returning JSON. If the model still answers in prose, the prose becomes the reply so the call never breaks.
- **REST, not streaming**, for STT and TTS: simpler and reliable within the time box. Next step: Gnani's WebSocket STT and TTS plus streaming LLM tokens to bring latency under 2 s.

## Assumptions (mock data beyond the brief)
60 active SKUs; 6 of the 18 out-of-stock SKUs were top sellers (86 orders last month); cancellation reasons (21 stock-outs, 9 late dispatch, 5 customer, 3 address); dispatch time 22 h → 41 h; search impressions 1.2 lakh → 82k; rating 4.3 → 4.1; 3 SKUs priced 8–13% above the lowest competitor; platform levers: a Savings Week sale (20–26 Nov), a ₹5,000 sponsored-listing credit, low-stock alerts, and Snapdeal fulfilment. The seller is "Rajesh Sharma, Sharma Home Essentials, Jaipur".
