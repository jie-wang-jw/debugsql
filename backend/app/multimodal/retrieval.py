from __future__ import annotations

import re

from app.multimodal.registry import build_media_match, load_assets
from app.multimodal.schemas import MediaMatch, MediaType


_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "find",
    "for",
    "in",
    "like",
    "look",
    "looks",
    "me",
    "of",
    "only",
    "show",
    "sound",
    "sounds",
    "that",
    "the",
    "to",
    "with",
}


def infer_media_type(message: str, previous: str | None = None) -> MediaType | None:
    text = message.lower()
    if any(term in text for term in ("image", "images", "photo", "picture", "pictures", "visual")):
        return "image"
    if any(term in text for term in ("audio", "sound", "sounds", "clip", "clips", "transcript")):
        return "audio"
    if any(term in text for term in ("video", "videos", "scene", "frames", "lecture")):
        return "video"
    if previous in {"image", "audio", "video"}:
        return previous  # type: ignore[return-value]
    return None


def extract_limit(message: str, default: int = 10) -> int:
    text = message.lower()
    match = re.search(r"\b(?:top|limit|first)(?:\s+to)?\s+(\d{1,3})\b", text)
    if not match:
        return default
    return max(1, min(int(match.group(1)), 100))


def extract_price_ceiling(message: str) -> float | None:
    text = message.lower()
    match = re.search(r"\b(?:under|below|less than|cheaper than)\s+\$?(\d+(?:\.\d+)?)\b", text)
    return float(match.group(1)) if match else None


def predicate_terms(message: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", message.lower())
    return [word for word in words if word not in _STOPWORDS and not word.isdigit()]


def term_overlap_fraction(asset, predicate: str) -> float:
    """Fraction of predicate terms found in the asset's caption/transcript/tags.

    Used by semantic SQL boolean membership: 1.0 means every meaningful term
    matched, 0.0 means none did.
    """
    terms = predicate_terms(predicate)
    if not terms:
        return 0.0
    haystack = " ".join([asset.caption, asset.transcript, " ".join(asset.tags)]).lower()
    return sum(1 for term in terms if term in haystack) / len(terms)


def search_media(
    predicate: str,
    *,
    media_type: MediaType | None = None,
    limit: int = 10,
) -> list[MediaMatch]:
    terms = predicate_terms(predicate)
    matches: list[MediaMatch] = []
    for asset in load_assets():
        if media_type and asset.media_type != media_type:
            continue
        haystack = " ".join([asset.caption, asset.transcript, " ".join(asset.tags)]).lower()
        overlap = sum(1 for term in terms if term in haystack)
        if overlap <= 0:
            continue
        score = min(0.99, 0.45 + overlap / max(len(terms), 1))
        matches.append(build_media_match(asset, score))
    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[:limit]
