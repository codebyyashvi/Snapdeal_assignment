import json
import re
import uuid
from datetime import datetime, timedelta, timezone

from . import llm
from .seller_data import SELLER, briefing, diagnose

def _calendar() -> str:
    today = datetime.now()
    days = [today + timedelta(days=i) for i in range(10)]
    return f"{today.strftime('%A, %d %B %Y')}. Upcoming days: " + ", ".join(d.strftime("%a %d %b") for d in days[1:])

SYSTEM_PROMPT = """You are Nalini, Snapdeal's AI Virtual Key Account Manager (KAM), speaking on a live VOICE call with a seller.
You are not a Q&A bot. You OWN this seller's sales problem: you have already analysed their account before the call,
you diagnose the root cause, confirm it with the seller, agree on a concrete action plan with owners and dates,
take on tasks yourself, and book a follow-up so the loop is closed.

Today is {today}.

## Seller account data (your own dashboard - use it, never invent other numbers)
{context}

## Previous call with this seller
{prior}

## How to speak (this is voice - it will be read aloud by TTS)
- 1 to 3 short sentences, under 50 words (up to 75 only when presenting the action plan). One question at a time. Never use numbered lists. Warm, confident, Indian-English business tone.
- Address the seller as "{first_name} ji". A light Hinglish touch like "ji" or "bilkul" is fine, but speak English.
- Use real dates from the calendar above (e.g. "by Friday, 13 November").
- NO markdown, bullets, emojis, symbols or abbreviations like Rs, INR, OOS, SKU, ASP, SLA, KAM.
- Say money and numbers the way an Indian speaks them: "2 lakh rupees", "1 lakh 35 thousand rupees", "65 thousand rupees", "14 percent".
- Lead with an insight from the data, then ask. Do not dump all the data at once - reveal it as the conversation progresses.
- If the seller is upset, acknowledge it in a few words, then move to the fix.

## Conversation playbook (move through stages; don't skip discovery)
1. discovery - Seller states the concern. Share the headline: sales fell about 32 percent because orders fell, price is unchanged, so this is a stock and fulfilment problem, not pricing. Then ask WHY their best-sellers went out of stock (supplier, cash flow, forecasting?).
2. diagnosis - Ask 1 or 2 follow-ups that change the recommendation: e.g. why dispatch time doubled (staff, courier, packing), or whether they can restock quickly. Connect cause and effect: stock-outs cause seller cancellations, cancellations plus slow dispatch cut rating and search visibility.
3. recommendation - Propose 2 or 3 prioritised, specific actions tailored to what the seller told you, each with expected impact in rupees or orders. Typical levers: restock the 6 best-sellers first (about 44 thousand rupees a month), turn on low-stock alerts and mark items out of stock instead of cancelling, fix dispatch to under 24 hours, then recover visibility via the Savings Week sale and sponsored-listing credit. Mention the price gap on 3 items only as a minor optional point.
4. commitment - Get the seller's agreement, set a due date for each action, and volunteer what YOU will do (e.g. nominate their top products for Savings Week, activate the 5 thousand rupee ad credit, send the restock list). Propose a follow-up call date about a week out.
5. closing - When the plan is agreed and the seller has nothing more, or wants to end, set stage "closing" and end_call true (the system will then speak the full recap).
If the seller asks something off-topic, answer briefly and steer back. If they push back on a recommendation, adapt it.

## Output
Return ONLY a JSON object:
{{
  "reply": "what you say out loud next",
  "stage": "discovery | diagnosis | recommendation | commitment | closing",
  "seller_facts": ["NEW facts the seller just told you, short phrases; [] if none"],
  "confirmed_issues": ["subset of: inventory, cancellations, visibility, pricing - issues now confirmed in conversation"],
  "action_plan": [
    {{"title": "short action", "owner": "seller | kam", "due": "e.g. 14 Nov", "impact": "short expected impact", "status": "proposed | agreed"}}
  ],
  "follow_up": {{"date": "e.g. 18 Nov", "purpose": "short"}} or null,
  "end_call": false
}}
action_plan is the COMPLETE current plan (keep earlier items, update status to agreed when the seller accepts). Leave it [] until you reach the recommendation stage.
"""

GREETING = (
    "Namaste {first_name} ji, this is Nalini, your Snapdeal Virtual Key Account Manager. "
    "I have your store dashboard open in front of me. How can I help you today?"
)
GREETING_RETURNING = (
    "Namaste {first_name} ji, Nalini here, your Snapdeal Virtual Key Account Manager. "
    "On our last call we agreed you would {action}. How is that going, and how can I help today?"
)

SUMMARY_PROMPT = """You are summarising a Snapdeal Virtual KAM voice call for the seller's case file.
Seller data and diagnosis:
{context}

Agreed action plan so far:
{plan}

Transcript:
{transcript}

Return ONLY JSON:
{{
  "key_issues": ["1-3 short sentences, the root causes confirmed"],
  "recommendations": ["2-3 specific actions with expected impact"],
  "next_steps": ["who does what by when, including the follow-up call"],
  "seller_sentiment": "one or two words",
  "spoken_summary": "a 40-60 word spoken closing recap for TTS: DO NOT start with any greeting (absolutely NO 'Hi', 'Hello', 'Namaste', or greeting the seller). Start directly with the recap or thank you (e.g. 'Thank you for your time today...', 'To summarize our discussion...'). No symbols, numbers said like '44 thousand rupees', ends with a warm goodbye"
}}
"""

SESSIONS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first_name() -> str:
    return SELLER["name"].split()[0]


def strip_leading_greeting(text: str) -> str:
    """Ensure closing statements don't start with greetings like 'Hi Rajesh ji,'."""
    if not text:
        return ""
    pattern = r"^(?:(?:Hi|Hello|Hey|Namaste|Good\s+(?:morning|afternoon|evening))\s*(?:[A-Za-z]+\s+)?(?:ji)?[\s,–—\-:]*)+"
    cleaned = re.sub(pattern, "", text.strip(), flags=re.IGNORECASE).strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned or text


def _prior_text(prior: dict | None) -> str:
    if not prior or not prior.get("summary"):
        return "None - this is the first call."
    s = prior["summary"]
    return json.dumps(
        {
            "date": prior.get("ended_at"),
            "key_issues": s.get("key_issues"),
            "next_steps": s.get("next_steps"),
            "action_plan": prior.get("action_plan"),
        }
    )


def new_session(prior: dict | None) -> dict:
    first = _first_name()
    prior_actions = [a for a in (prior or {}).get("action_plan", []) if a.get("owner") == "seller"]
    if prior_actions:
        greeting = GREETING_RETURNING.format(first_name=first, action=prior_actions[0]["title"].rstrip(".").lower())
    else:
        greeting = GREETING.format(first_name=first)

    session = {
        "id": uuid.uuid4().hex[:12],
        "seller_id": SELLER["seller_id"],
        "started_at": _now(),
        "ended_at": None,
        "stage": "greeting",
        "transcript": [{"role": "assistant", "text": greeting, "ts": _now()}],
        "seller_facts": [],
        "confirmed_issues": [],
        "action_plan": [],
        "follow_up": None,
        "summary": None,
        "llm_provider": None,
        "prior": _prior_text(prior),
    }
    SESSIONS[session["id"]] = session
    return session


MAX_TURNS_IN_PROMPT = 14


def _system_message(session: dict) -> dict:
    return {
        "role": "system",
        "content": SYSTEM_PROMPT.format(
            today=_calendar(),
            context=briefing(),
            prior=session["prior"],
            first_name=_first_name(),
        ),
    }


def _transcript_text(session: dict, limit: int | None = None) -> str:
    turns = session["transcript"][-limit:] if limit else session["transcript"]
    return "\n".join(f"{'KAM' if t['role'] == 'assistant' else 'Seller'}: {t['text']}" for t in turns)


def _turn_message(session: dict) -> dict:
    # The whole call goes in one user message: if past KAM turns were sent as plain assistant
    # messages, the model imitates them and stops emitting JSON.
    state = {
        "stage": session["stage"],
        "seller_facts": session["seller_facts"],
        "confirmed_issues": session["confirmed_issues"],
        "action_plan": session["action_plan"],
        "follow_up": session["follow_up"],
    }
    return {
        "role": "user",
        "content": f"Call transcript so far:\n{_transcript_text(session, MAX_TURNS_IN_PROMPT)}\n\n"
        f"Current call state: {json.dumps(state)}\n\n"
        "Write the KAM's next turn. Respond with ONLY the JSON object from the Output section.",
    }


async def take_turn(session: dict, user_text: str) -> dict:
    session["transcript"].append({"role": "user", "text": user_text, "ts": _now()})

    messages = [_system_message(session), _turn_message(session)]
    out, provider = await llm.chat_json(messages, text_key="reply")

    reply = (out.get("reply") or "").strip() or "Sorry, could you say that once more?"
    session["llm_provider"] = provider
    session["stage"] = out.get("stage") or session["stage"]
    for fact in out.get("seller_facts") or []:
        if fact and fact not in session["seller_facts"]:
            session["seller_facts"].append(fact)
    if out.get("confirmed_issues"):
        session["confirmed_issues"] = sorted(set(session["confirmed_issues"]) | set(out["confirmed_issues"]))
    if out.get("action_plan"):
        session["action_plan"] = out["action_plan"]
    if out.get("follow_up"):
        session["follow_up"] = out["follow_up"]

    session["transcript"].append({"role": "assistant", "text": reply, "ts": _now()})
    return {"reply": reply, "end_call": bool(out.get("end_call"))}


async def summarize(session: dict) -> dict:
    transcript = _transcript_text(session)
    summary, _ = await llm.chat_json(
        [
            {
                "role": "user",
                "content": SUMMARY_PROMPT.format(
                    context=diagnose()["headline"],
                    plan=json.dumps(session["action_plan"]),
                    transcript=transcript,
                ),
            }
        ],
        max_tokens=800,
        temperature=0.2,
    )
    if summary.get("spoken_summary"):
        summary["spoken_summary"] = strip_leading_greeting(summary["spoken_summary"])
    session["summary"] = summary
    session["ended_at"] = _now()
    session["stage"] = "closed"
    return summary
