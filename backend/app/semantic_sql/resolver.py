from __future__ import annotations

from typing import Protocol

from app.config import get_settings
from app.semantic_sql.schemas import NLFilterOp, ResolvedMatch


class SemanticResolver(Protocol):
    """Pluggable predicate resolver.

    The keyword implementation below can later be replaced by an
    embedding/vision model without changing the SQL interface.
    """

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]: ...


class KeywordMediaResolver:
    """Resolves NL_FILTER predicates over media_assets via keyword/tag overlap.

    This intentionally reuses the existing retrieval layer; it does not fake
    vision results. Matches below the configured score cutoff are excluded
    (boolean membership semantics).
    """

    SUPPORTED_TABLE = "media_assets"

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        from app.multimodal.registry import load_assets
        from app.multimodal.retrieval import term_overlap_fraction

        settings = get_settings()
        cutoff = settings.semantic_sql_score_cutoff
        matches = [
            ResolvedMatch(key=asset.id, score=round(score, 4))
            for asset in load_assets()
            if (score := term_overlap_fraction(asset, op.predicate)) >= cutoff and score > 0
        ]
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[: settings.semantic_sql_max_matches]
