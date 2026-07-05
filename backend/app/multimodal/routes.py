from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.multimodal.registry import dataset_info, get_asset, resolve_asset_path
from app.request_auth import request_user_id


router = APIRouter(prefix="/multimodal", tags=["multimodal"])


@router.get("/datasets")
def datasets(request: Request) -> dict:
    """Backward-compatible alias for the unified benchmark registry."""
    request_user_id(request)
    from app.benchmarks.registry import find_descriptor

    payload = dataset_info()
    descriptor = find_descriptor("multimodal_demo")
    if descriptor is not None:
        payload = {
            **payload,
            "modalities": descriptor.modalities,
            "capabilities": descriptor.capabilities,
            "connector": descriptor.connector,
        }
    return {"success": True, "data": [payload]}


@router.get("/assets/{asset_id}")
def asset(asset_id: str, request: Request) -> dict:
    request_user_id(request)
    found = get_asset(asset_id)
    if found is None:
        return {"success": False, "error": "Media asset not found."}
    return {"success": True, "data": found.model_dump()}


@router.get("/assets/{asset_id}/preview")
def preview(asset_id: str, request: Request) -> FileResponse:
    request_user_id(request)
    path = resolve_asset_path(asset_id)
    return FileResponse(path)
