from __future__ import annotations

from app.config import get_settings
from app.craigslist.registry import image_search_documents, title_search_documents, token_overlap
from app.semantic_sql.schemas import NLFilterOp, ResolvedMatch


class CraigslistLabelResolver:
    """Resolve semantic predicates against the benchmark's prepared labels."""

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        if op.table == "images" and op.column == "img":
            documents = image_search_documents()
        elif op.table == "furniture" and op.column in {"title", "title_u"}:
            documents = title_search_documents()
        else:
            return []

        settings = get_settings()
        matches = [
            ResolvedMatch(key=key, score=round(score, 4))
            for key, document in documents.items()
            if (score := token_overlap(document, op.predicate)) >= settings.semantic_sql_score_cutoff
            and score > 0
        ]
        matches.sort(key=lambda item: item.score, reverse=True)
        return matches[: settings.semantic_sql_max_matches]
