from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.craigslist import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run leakage-free DebugSQL evaluations")
    parser.add_argument("run", choices=["run"])
    parser.add_argument("--benchmark", choices=["craigslist"], required=True)
    parser.add_argument("--mode", choices=["clip-only", "clip+vlm"], required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark(args.mode, args.output)
    summary = {
        "benchmark": report["benchmark"],
        "mode": report["mode"],
        "queryCount": report["queryCount"],
        "selectionExecutionAccuracy": report["selectionExecutionAccuracy"],
        "meanRelativeAggregateError": report["meanRelativeAggregateError"],
        "latencyMs": report["latencyMs"],
        "visionRequestCount": report["visionRequestCount"],
        "visionScoredImageCount": report["visionScoredImageCount"],
        "output": str(args.output.resolve()) if args.output else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
