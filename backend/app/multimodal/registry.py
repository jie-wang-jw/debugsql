from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import get_settings
from app.multimodal.schemas import MediaAsset, MediaMatch, MultimodalEntity


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def multimodal_root() -> Path:
    configured = Path(get_settings().multimodal_data_dir)
    return configured if configured.is_absolute() else PROJECT_ROOT / configured


@lru_cache(maxsize=1)
def load_entities() -> list[MultimodalEntity]:
    path = multimodal_root() / "metadata" / "entities.json"
    if not path.exists():
        return []
    return [MultimodalEntity.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


@lru_cache(maxsize=1)
def load_assets() -> list[MediaAsset]:
    path = multimodal_root() / "metadata" / "assets.json"
    if not path.exists():
        return []
    return [MediaAsset.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]


def dataset_info() -> dict[str, Any]:
    assets = load_assets()
    return {
        "id": "multimodal_demo",
        "label": "Multimodal Demo",
        "status": "ready" if assets else "missing",
        "entityCount": len(load_entities()),
        "mediaCounts": {
            "image": sum(1 for asset in assets if asset.media_type == "image"),
            "audio": sum(1 for asset in assets if asset.media_type == "audio"),
            "video": sum(1 for asset in assets if asset.media_type == "video"),
        },
    }


def get_asset(asset_id: str) -> MediaAsset | None:
    return next((asset for asset in load_assets() if asset.id == asset_id), None)


def resolve_asset_path(asset_id: str) -> Path:
    asset = get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found.")
    root = multimodal_root().resolve()
    target = (root / asset.file_path).resolve()
    if root not in target.parents and target != root:
        raise HTTPException(status_code=400, detail="Invalid media asset path.")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Media file not found.")
    return target


def media_preview_url(asset_id: str) -> str:
    return f"/api/multimodal/assets/{asset_id}/preview"


def build_media_match(asset: MediaAsset, score: float) -> MediaMatch:
    return MediaMatch(
        asset_id=asset.id,
        entity_id=asset.entity_id,
        media_type=asset.media_type,
        score=round(score, 4),
        file_path=asset.file_path,
        preview_url=media_preview_url(asset.id),
        caption=asset.caption,
        transcript=asset.transcript,
        tags=asset.tags,
        metadata=asset.metadata,
    )
