from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse

from app.craigslist.registry import resolve_image_path
from app.request_auth import request_user_id


router = APIRouter(prefix="/craigslist", tags=["craigslist"])


@router.get("/preview")
def preview(request: Request, img: str = Query(...)) -> FileResponse:
    request_user_id(request)
    return FileResponse(resolve_image_path(img))
