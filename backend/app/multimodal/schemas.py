from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MediaType = Literal["image", "audio", "video", "text"]


class MediaAsset(BaseModel):
    id: str
    media_type: MediaType
    file_path: str
    entity_id: str
    caption: str = ""
    transcript: str = ""
    tags: list[str] = Field(default_factory=list)
    source_table: str = "entities"
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultimodalEntity(BaseModel):
    id: str
    name: str
    category: str = ""
    price: float | None = None
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaMatch(BaseModel):
    asset_id: str
    entity_id: str
    media_type: MediaType
    score: float
    file_path: str
    preview_url: str
    caption: str = ""
    transcript: str = ""
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MultimodalQueryPlan(BaseModel):
    answer: str
    sql: str
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    media_matches: list[MediaMatch] = Field(default_factory=list)
    media_predicate: str
    media_type: MediaType | None = None
    limit: int = 10
    used_context: bool = False
