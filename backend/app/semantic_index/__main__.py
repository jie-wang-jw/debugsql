from __future__ import annotations

import argparse
import json

from app.semantic_index.builder import build_craigslist_indexes


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DebugSQL semantic indexes")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--benchmark", choices=["craigslist"], required=True)
    args = parser.parse_args()
    if args.command == "build" and args.benchmark == "craigslist":
        print(json.dumps(build_craigslist_indexes(), indent=2))


if __name__ == "__main__":
    main()
