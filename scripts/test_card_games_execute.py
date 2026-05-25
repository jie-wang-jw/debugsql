"""Debug card_games execution payload shape."""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
QUESTION = "Which are the cards that have incredibly powerful foils."


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def get(url: str) -> dict:
    return json.loads(urllib.request.urlopen(url, timeout=15).read())


def main() -> None:
    chat = post(
        f"{BASE}/query",
        {
            "message": QUESTION,
            "sessionId": "debug-card-games",
            "datasetContext": {"benchmark": "bird", "dbId": "card_games"},
        },
    )
    data = chat["data"]
    print("chat sql preview:", (data.get("sql") or "")[:120])
    plan_id = data["planId"]
    run = post(
        f"{BASE}/execute",
        {"sql": data.get("sql") or "", "planId": plan_id},
    )["data"]
    result = get(f"{BASE}/execute/{run['runId']}/result")["data"]
    print("columns:", result.get("columns"))
    print("row0:", result.get("rows", [None])[0])
    print("row0 keys:", list((result.get("rows") or [{}])[0].keys()))
    print("rowCount metric:", result.get("metrics", {}).get("rowCount"))


if __name__ == "__main__":
    main()
