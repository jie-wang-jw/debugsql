from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Modality = Literal["table", "text", "image", "audio", "video"]

Capability = Literal[
    "structured_sql",
    "cross_table_join",
    "image_semantic_predicate",
    "audio_semantic_predicate",
    "video_semantic_predicate",
    "ai_fuzzy_match",
]

# Human-readable labels for the "This benchmark supports" panel. Kept on the
# backend so the frontend never hardcodes capability copy.
CAPABILITY_LABELS: dict[str, str] = {
    "structured_sql": "Structured SQL filters",
    "cross_table_join": "Cross-table joins",
    "image_semantic_predicate": "Image semantic predicates",
    "audio_semantic_predicate": "Audio semantic predicates",
    "video_semantic_predicate": "Video semantic predicates",
    "ai_fuzzy_match": "AI-based fuzzy matching in WHERE / JOIN",
}


class BenchmarkDescriptor(BaseModel):
    """Single, capability-aware view of a benchmark family.

    This is the unified object surfaced by ``GET /benchmarks`` and by the
    capabilities endpoint. It intentionally keeps the legacy
    ``id/label/status/databaseCount`` keys so the existing frontend selector
    keeps working, while adding ``modalities`` / ``capabilities`` / ``connector``.
    """

    id: str
    label: str
    status: Literal["ready", "missing", "partial"] = "missing"
    connector: str
    modalities: list[Modality] = Field(default_factory=lambda: ["table"])
    capabilities: list[Capability] = Field(default_factory=lambda: ["structured_sql"])
    databaseCount: int = 0
    description: str = ""
    extra: dict = Field(default_factory=dict)

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def capability_labels(self) -> list[str]:
        return [CAPABILITY_LABELS.get(cap, cap) for cap in self.capabilities]
