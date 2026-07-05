from __future__ import annotations

from app.multimodal.registry import load_entities
from app.multimodal.retrieval import extract_limit, extract_price_ceiling, infer_media_type, search_media
from app.multimodal.schemas import MultimodalQueryPlan


def resolve_multimodal_query(
    message: str,
    working_state: dict | None = None,
) -> MultimodalQueryPlan:
    previous = working_state or {}
    previous_media_type = previous.get("mediaType") if isinstance(previous.get("mediaType"), str) else None
    previous_predicate = previous.get("mediaPredicate") if isinstance(previous.get("mediaPredicate"), str) else None
    media_type = infer_media_type(message, previous_media_type)
    limit = extract_limit(message, default=int(previous.get("limit") or 10))
    predicate = message
    if previous_predicate and _looks_like_refinement(message):
        predicate = previous_predicate
    price_ceiling = extract_price_ceiling(message)
    if price_ceiling is None and previous.get("priceCeiling") is not None and _looks_like_refinement(message):
        price_ceiling = float(previous["priceCeiling"])

    matches = search_media(predicate, media_type=media_type, limit=limit * 3)
    entity_by_id = {entity.id: entity for entity in load_entities()}
    if price_ceiling is not None:
        matches = [
            match for match in matches
            if (entity_by_id.get(match.entity_id) and (entity_by_id[match.entity_id].price or 0) < price_ceiling)
        ]
    matches = matches[:limit]
    sql = _build_sql(matches, limit=limit, price_ceiling=price_ceiling)
    kind = media_type or "media"
    answer = f"I found {len(matches)} {kind} matches for this request."
    explanation = (
        "I searched the prepared multimodal asset metadata, ranked matching media by text overlap, "
        "then joined the matched asset ids with the prepared entity table for read-only SQL execution."
    )
    assumptions = [
        "This demo uses prepared captions/transcripts as the retrieval index; embedding providers can replace this layer later.",
    ]
    if not matches:
        assumptions.append("No prepared media asset matched the requested media predicate.")
    return MultimodalQueryPlan(
        answer=answer,
        sql=sql,
        explanation=explanation,
        assumptions=assumptions,
        media_matches=matches,
        media_predicate=predicate,
        media_type=media_type,
        limit=limit,
        used_context=bool(previous_predicate and _looks_like_refinement(message)),
    )


def _looks_like_refinement(message: str) -> bool:
    text = message.lower().strip()
    return any(term in text for term in ("limit", "top", "only", "under", "below", "sort", "cheapest", "similar"))


def _build_sql(matches, *, limit: int, price_ceiling: float | None) -> str:
    values = ", ".join(
        f"('{match.asset_id.replace(chr(39), chr(39) * 2)}', {match.score:.4f})"
        for match in matches
    ) or "('__no_match__', 0.0)"
    where = ""
    if price_ceiling is not None:
        where = f"\nWHERE e.price < {price_ceiling:g}"
    return (
        "WITH media_matches(asset_id, score) AS (VALUES "
        f"{values})\n"
        "SELECT e.id AS entity_id, e.name, e.category, e.price, "
        "a.id AS asset_id, a.media_type, a.caption, media_matches.score\n"
        "FROM media_matches\n"
        "JOIN media_assets a ON a.id = media_matches.asset_id\n"
        "JOIN entities e ON e.id = a.entity_id"
        f"{where}\n"
        "ORDER BY media_matches.score DESC\n"
        f"LIMIT {limit};"
    )
