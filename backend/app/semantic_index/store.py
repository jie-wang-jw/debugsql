from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.config import get_settings


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _data_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else _REPO_ROOT / path


def craigslist_index_dir() -> Path:
    return _data_path(get_settings().semantic_index_dir) / "craigslist"


def load_manifest() -> dict:
    path = craigslist_index_dir() / "manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def craigslist_index_status() -> dict:
    root = craigslist_index_dir()
    manifest_path = root / "manifest.json"
    required = ("image_embeddings.npy", "image_ids.json", "title_embeddings.npy", "title_ids.json")
    if not manifest_path.is_file() or not all((root / name).is_file() for name in required):
        return {
            "indexStatus": "missing",
            "imageModel": f"{get_settings().clip_model}/{get_settings().clip_pretrained}",
            "indexedImageCount": 0,
            "visionReranker": get_settings().vision_model,
        }
    try:
        manifest = load_manifest()
        if not manifest:
            raise ValueError("empty manifest")
    except ValueError:
        return {"indexStatus": "corrupt", "indexedImageCount": 0}
    return {
        "indexStatus": "ready",
        "imageModel": manifest.get("imageModel", ""),
        "indexedImageCount": int(manifest.get("indexedImageCount", 0)),
        "visionReranker": get_settings().vision_model,
    }


@dataclass(frozen=True)
class VectorIndex:
    ids: list[str]
    vectors: object


@lru_cache(maxsize=2)
def load_index(kind: str) -> VectorIndex:
    if kind not in {"image", "title"}:
        raise ValueError(f"Unknown index kind: {kind}")
    import numpy as np

    root = craigslist_index_dir()
    ids = json.loads((root / f"{kind}_ids.json").read_text(encoding="utf-8"))
    vectors = np.load(root / f"{kind}_embeddings.npy", mmap_mode="r")
    if len(ids) != len(vectors):
        raise RuntimeError(f"{kind} index IDs and vectors have different lengths")
    return VectorIndex(ids=[str(item) for item in ids], vectors=vectors)
