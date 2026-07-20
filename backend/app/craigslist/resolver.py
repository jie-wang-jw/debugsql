from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.craigslist.vision import VisionProviderError, VisionReranker
from app.semantic_index.store import load_index
from app.semantic_sql.schemas import NLFilterOp, ResolvedMatch, SemanticSQLError


@lru_cache(maxsize=1)
def _clip_runtime():
    import open_clip

    settings = get_settings()
    model, _, _ = open_clip.create_model_and_transforms(
        settings.clip_model, pretrained=settings.clip_pretrained
    )
    model.eval()
    return model, open_clip.get_tokenizer(settings.clip_model)


@lru_cache(maxsize=1)
def _title_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(get_settings().text_embedding_model)


def _rank(ids: list[str], vectors, query, count: int) -> list[tuple[str, float]]:
    import numpy as np

    scores = np.asarray(vectors @ query, dtype="float32")
    count = min(max(count, 1), len(scores))
    indexes = np.argpartition(scores, -count)[-count:]
    indexes = indexes[np.argsort(scores[indexes])[::-1]]
    return [(ids[int(index)], float(scores[int(index)])) for index in indexes]


class CraigslistImageResolver:
    def __init__(
        self,
        *,
        use_vision: bool | None = None,
        reranker: VisionReranker | None = None,
    ) -> None:
        self.use_vision = use_vision
        self.reranker = reranker or VisionReranker()

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        if op.table != "images" or op.column != "img":
            return []
        import torch

        settings = get_settings()
        try:
            index = load_index("image")
        except (OSError, RuntimeError, ValueError) as exc:
            raise SemanticSQLError(
                "Craigslist image index is unavailable. Run: "
                "python -m app.semantic_index build --benchmark craigslist"
            ) from exc
        model, tokenizer = _clip_runtime()
        with torch.no_grad():
            encoded = model.encode_text(tokenizer([op.predicate]))
            encoded /= encoded.norm(dim=-1, keepdim=True)
        clip = _rank(
            index.ids, index.vectors, encoded[0].cpu().numpy(), settings.clip_candidate_count
        )
        # Convert cosine similarity to a stable [0, 1] score for combination.
        clip = [(image_id, max(0.0, min(1.0, (score + 1.0) / 2.0))) for image_id, score in clip]
        if self.use_vision is False:
            combined = clip
        else:
            shortlist = clip[: settings.vision_rerank_count]
            try:
                vision = self.reranker.rerank(op.predicate, shortlist)
                combined = [
                    (image_id, 0.35 * clip_score + 0.65 * vision[image_id])
                    for image_id, clip_score in shortlist
                ]
            except VisionProviderError as exc:
                allow_baseline = settings.vision_allow_clip_only and self.use_vision is None
                if not allow_baseline:
                    raise SemanticSQLError(str(exc)) from exc
                combined = clip
        combined.sort(key=lambda item: item[1], reverse=True)
        return [
            ResolvedMatch(key=image_id, score=round(score, 4))
            for image_id, score in combined
            if score >= settings.semantic_sql_score_cutoff
        ][: settings.semantic_sql_max_matches]


class CraigslistTitleResolver:
    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        if op.table != "furniture" or op.column not in {"title", "title_u"}:
            return []
        import numpy as np

        settings = get_settings()
        try:
            index = load_index("title")
        except (OSError, RuntimeError, ValueError) as exc:
            raise SemanticSQLError(
                "Craigslist title index is unavailable. Run the semantic index builder first."
            ) from exc
        query = _title_model().encode([op.predicate], normalize_embeddings=True)[0]
        ranked = _rank(index.ids, index.vectors, np.asarray(query), settings.clip_candidate_count)
        return [
            ResolvedMatch(key=aid, score=round(score, 4))
            for aid, score in ranked
            if score >= settings.semantic_sql_score_cutoff
        ][: settings.semantic_sql_max_matches]


class CraigslistSemanticResolver:
    def __init__(self, *, use_vision: bool | None = None) -> None:
        self.image = CraigslistImageResolver(use_vision=use_vision)
        self.title = CraigslistTitleResolver()

    def resolve_filter(self, op: NLFilterOp) -> list[ResolvedMatch]:
        if op.table == "images":
            return self.image.resolve_filter(op)
        if op.table == "furniture":
            return self.title.resolve_filter(op)
        return []
