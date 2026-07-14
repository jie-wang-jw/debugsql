from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException

from app.benchmark_registry import BENCHMARK_ROOT


_REQUIRED_FILES = (
    "furnitures.csv",
    "imgs.csv",
    "craigslist_furnitures_title_label.json",
    "craigslist_imgs_label.json",
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
def title_search_documents() -> dict[str, str]:
    labels = _load_json("craigslist_furnitures_title_label.json")
    titles = {row["aid"]: str(row.get("title") or "") for row in load_furniture()}
    return {
        str(item.get("aid") or ""): " ".join([titles.get(str(item.get("aid") or ""), ""), *_label_values(item)])
        for item in labels
        if item.get("aid") is not None
    }


@lru_cache(maxsize=1)
def image_search_documents() -> dict[str, str]:
    labels = _load_json("craigslist_imgs_label.json")
    return {
        str(item.get("img") or ""): " ".join(_label_values(item))
        for item in labels
        if item.get("img")
    }


@lru_cache(maxsize=1)
def images_by_aid() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in load_images():
        result.setdefault(row["aid"], []).append(row["img"])
    return result


def media_preview(img: str, score: float = 0.0) -> dict[str, Any] | None:
    known = image_search_documents()
    if img not in known:
        return None
    aid = next((row["aid"] for row in load_images() if row["img"] == img), "")
    return {
        "asset_id": img,
        "entity_id": aid,
        "media_type": "image",
        "score": score,
        "file_path": img,
        "preview_url": f"/api/craigslist/preview?img={quote(img, safe='')}",
        "caption": known[img],
        "transcript": "",
        "tags": [],
        "metadata": {"aid": aid},
    }


def resolve_image_path(img: str) -> Path:
    if img not in image_search_documents():
        raise HTTPException(status_code=404, detail="Craigslist image not found.")
    candidate = (craigslist_root() / "furniture_imgs" / Path(img).name).resolve()
    allowed = (craigslist_root() / "furniture_imgs").resolve()
    if allowed not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Craigslist image file not found.")
    return candidate


def dataset_info() -> dict[str, Any]:
    return {
        "id": "craigslist",
        "label": "Craigslist Furniture",
        "status": "ready" if dataset_ready() else "missing",
        "listingCount": len(load_furniture()) if dataset_ready() else 0,
        "imageCount": len(load_images()) if dataset_ready() else 0,
    }


def token_overlap(document: str, predicate: str) -> float:
    query_terms = _terms(predicate)
    if not query_terms:
        return 0.0
    document_terms = _terms(document)
    return len(query_terms & document_terms) / len(query_terms)


def _load_json(name: str) -> list[dict[str, Any]]:
    path = craigslist_root() / name
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _label_values(item: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in item.items():
        if key in {"aid", "img"} or value is None:
            continue
        if isinstance(value, list):
            values.extend(str(part) for part in value)
        else:
            values.append(str(value))
    return values


def _terms(value: str) -> set[str]:
    aliases = {"wooden": "wood", "chairs": "chair", "tables": "table", "sofas": "sofa"}
    ignored = {"a", "an", "and", "find", "for", "image", "images", "in", "like", "look", "looking", "of", "show", "that", "the", "with"}
    terms = set()
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        normalized = aliases.get(token, token)
        if normalized not in ignored:
            terms.add(normalized)
    return terms


def _number(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
