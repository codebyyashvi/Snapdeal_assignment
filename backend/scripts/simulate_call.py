"""Drive a full call through the API in text mode to check agent behaviour."""
import json
import sys

import httpx

API = "http://127.0.0.1:8000/api"
SELLER_LINES = [
    "My sales have dropped significantly this month. I don't understand why. Can you help me?",
    "Haan, my supplier in Delhi delayed two shipments, and I also had some cash flow issues so I could not reorder in time.",
    "Also one of my two packing staff left this month, so dispatch is getting late.",
    "Okay, that makes sense. I can restock the top items by this Friday. What else should I do?",
    "Yes, please nominate my products for the sale. That sounds good.",
    "No, that's all. Thank you so much.",
]

c = httpx.Client(timeout=90)
r = c.post(f"{API}/session").json()
sid = r["state"]["id"]
print("KAM:", r["reply"])
for line in SELLER_LINES:
    print("\nSELLER:", line)
    r = c.post(f"{API}/session/{sid}/turn", data={"text": line}).json()
    s = r["state"]
    print(f"KAM [{s['stage']}] ({r['timings']}):", r["reply"])
    if r["end_call"]:
        break
if not r["end_call"]:
    r = c.post(f"{API}/session/{sid}/end").json()
    print("\nKAM (end):", r["reply"])
s = r["state"]
print("\nFACTS:", s["seller_facts"])
print("ISSUES:", s["confirmed_issues"])
print("PLAN:", json.dumps(s["action_plan"], indent=1))
print("FOLLOW-UP:", s["follow_up"])
print("SUMMARY:", json.dumps(s["summary"], indent=1))
sys.exit(0)
