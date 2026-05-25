"""Quick smoke test for BIRD benchmark API."""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def get(url: str) -> dict:
    return json.loads(urllib.request.urlopen(url, timeout=15).read())


def post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def main() -> None:
    financial = next(
        item
        for item in get(f"{BASE}/benchmarks/bird/databases")["data"]
        if item["dbId"] == "financial"
    )
    print("financial hasSQLite:", financial["hasSQLite"])

    question = financial["sampleQuestions"][0]["question"]
    chat = post(
        f"{BASE}/query",
        {
            "message": question,
            "sessionId": "bird-smoke-test",
            "datasetContext": {"benchmark": "bird", "dbId": "financial"},
        },
    )["data"]
    print("intent:", chat.get("intentType"), "planId:", chat.get("planId"))

    if not chat.get("planId"):
        return

    run = post(
        f"{BASE}/execute",
        {"sql": chat.get("sql"), "planId": chat["planId"]},
    )["data"]
    result = get(f"{BASE}/execute/{run['runId']}/result")["data"]
    print("rowCount:", result.get("metrics", {}).get("rowCount"))
    if result.get("rows"):
        print("first row:", result["rows"][0])


if __name__ == "__main__":
    main()
