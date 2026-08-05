from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException

from app.benchmark_registry import BENCHMARK_ROOT


_REQUIRED_FILES = (
    "furnitures.csv",
    "imgs.csv",
)


def craigslist_root() -> Path:
    for name in ("Craigslist", "craigslist"):
        candidate = BENCHMARK_ROOT / name
        if candidate.exists():
            return candidate
    return BENCHMARK_ROOT / "Craigslist"


def dataset_ready() -> bool:
    root = craigslist_root()
    return all((root / name).is_file() for name in _REQUIRED_FILES) and (root / "furniture_imgs").is_dir()


@lru_cache(maxsize=1)
def load_furniture() -> list[dict[str, Any]]:
    path = craigslist_root() / "furnitures.csv"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["price"] = _number(row.get("price"))
        row["aid"] = str(row.get("aid") or "")
        row["title_u"] = str(row.get("title") or "")
    return rows


@lru_cache(maxsize=1)
def load_images() -> list[dict[str, str]]:
    path = craigslist_root() / "imgs.csv"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {"img": str(row.get("img") or ""), "aid": str(row.get("aid") or "")}
            for row in csv.DictReader(handle)
        ]


@lru_cache(maxsize=1)
def furniture_by_aid() -> dict[str, dict[str, Any]]:
    return {row["aid"]: row for row in load_furniture()}


@lru_cache(maxsize=1)
def image_to_aid() -> dict[str, str]:
    return {row["img"]: row["aid"] for row in load_images() if row["img"]}


@lru_cache(maxsize=1)
def images_by_aid() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in load_images():
        result.setdefault(row["aid"], []).append(row["img"])
    return result


def media_preview(img: str, score: float = 0.0) -> dict[str, Any] | None:
    known = image_to_aid()
    if img not in known:
        return None
    aid = known[img]
    listing = furniture_by_aid().get(aid, {})
    return {
        "asset_id": img,
        "entity_id": aid,
        "media_type": "image",
        "score": score,
        "file_path": img,
        "preview_url": f"/api/craigslist/preview?img={quote(img, safe='')}",
        "caption": str(listing.get("title") or ""),
        "price": listing.get("price"),
        "transcript": "",
        "tags": [],
        "metadata": {"aid": aid, "price": listing.get("price")},
    }


def resolve_image_path(img: str) -> Path:
    if img not in image_to_aid():
        raise HTTPException(status_code=404, detail="Craigslist image not found.")
    candidate = (craigslist_root() / "furniture_imgs" / Path(img).name).resolve()
    allowed = (craigslist_root() / "furniture_imgs").resolve()
    if allowed not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Craigslist image file not found.")
    return candidate


def dataset_info() -> dict[str, Any]:
    from app.semantic_index.store import craigslist_index_status

    index = craigslist_index_status()
    raw_ready = dataset_ready()
    return {
        "id": "craigslist",
        "label": "Craigslist Furniture",
        "status": "ready" if raw_ready and index["indexStatus"] == "ready" else ("partial" if raw_ready else "missing"),
        "listingCount": len(load_furniture()) if raw_ready else 0,
        "imageCount": len(load_images()) if raw_ready else 0,
        **index,
    }


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
