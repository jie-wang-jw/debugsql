from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import sqlite3
from io import BytesIO
from pathlib import Path

from openai import OpenAI
from PIL import Image

from app.config import get_settings
from app.craigslist.registry import resolve_image_path
from app.semantic_index.store import craigslist_index_dir, load_manifest


class VisionProviderError(RuntimeError):
    pass


class VisionReranker:
    batch_size = 8

    def __init__(self) -> None:
        self.request_count = 0
        self.scored_image_count = 0

    def rerank(self, predicate: str, candidates: list[tuple[str, float]]) -> dict[str, float]:
        settings = get_settings()
        selected = candidates[: settings.vision_rerank_count]
        cached, missing = self._read_cache(predicate, selected)
        if missing:
            if not settings.vision_api_key or not settings.vision_api_base_url:
                raise VisionProviderError(
                    "Vision reranking is required but VISION_API_KEY is not configured. "
                    "Set VISION_ALLOW_CLIP_ONLY=true only for a documented CLIP baseline."
                )
            for start in range(0, len(missing), self.batch_size):
                batch = missing[start:start + self.batch_size]
                generated = self._request(predicate, batch)
                self._write_cache(predicate, batch, generated)
                cached.update(generated)
        return cached

    def _request(self, predicate: str, candidates: list[tuple[str, float]]) -> dict[str, float]:
        settings = get_settings()
        content: list[dict] = [{
            "type": "text",
            "text": (
                "Score how well each image matches this visual predicate: " + predicate +
                ". Return only JSON: {\"scores\":[{\"id\":\"...\",\"score\":0.0}]}. "
                "Include every supplied ID exactly once; scores must be between 0 and 1."
            ),
        }]
        for image_id, _ in candidates:
            path = resolve_image_path(image_id)
            mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
            encoded = base64.b64encode(_resized_jpeg(path)).decode("ascii")
            content.append({"type": "text", "text": f"Image ID: {image_id}"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "low"},
            })
        try:
            self.request_count += 1
            self.scored_image_count += len(candidates)
            response = OpenAI(
                api_key=settings.vision_api_key,
                base_url=settings.vision_api_base_url,
                timeout=settings.vision_timeout_seconds,
            ).chat.completions.create(
                model=settings.vision_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": content}],
            )
            payload = json.loads(response.choices[0].message.content or "{}")
        except Exception as exc:
            raise VisionProviderError(f"Vision reranking failed: {exc}") from exc
        expected = {image_id for image_id, _ in candidates}
        scores: dict[str, float] = {}
        for item in payload.get("scores", []):
            image_id = str(item.get("id") or "")
            score = item.get("score")
            if image_id not in expected or image_id in scores or not isinstance(score, (int, float)):
                raise VisionProviderError("Vision response contains invalid or duplicate image IDs.")
            if not 0 <= float(score) <= 1:
                raise VisionProviderError("Vision response scores must be between 0 and 1.")
            scores[image_id] = float(score)
        if set(scores) != expected:
            raise VisionProviderError("Vision response did not score every shortlisted image.")
        return scores

    def _cache_key(self, predicate: str, image_id: str) -> str:
        settings = get_settings()
        checksum = str(load_manifest().get("imageChecksums", {}).get(image_id) or "")
        if not checksum:
            checksum = hashlib.sha256(resolve_image_path(image_id).read_bytes()).hexdigest()
        raw = "|".join((
            "craigslist", image_id, checksum, " ".join(predicate.lower().split()),
            settings.vision_provider, settings.vision_model,
        ))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _connection(self) -> sqlite3.Connection:
        path = craigslist_index_dir() / "vision_scores.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS scores (cache_key TEXT PRIMARY KEY, score REAL NOT NULL)")
        return conn

    def _read_cache(self, predicate, candidates):
        cached: dict[str, float] = {}
        missing = []
        with self._connection() as conn:
            for image_id, clip_score in candidates:
                row = conn.execute("SELECT score FROM scores WHERE cache_key=?", (self._cache_key(predicate, image_id),)).fetchone()
                if row:
                    cached[image_id] = float(row[0])
                else:
                    missing.append((image_id, clip_score))
        return cached, missing

    def _write_cache(self, predicate, candidates, scores):
        with self._connection() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO scores(cache_key, score) VALUES (?, ?)",
                [(self._cache_key(predicate, image_id), scores[image_id]) for image_id, _ in candidates],
            )


def _resized_jpeg(path: Path, max_side: int = 768) -> bytes:
    with Image.open(path) as image:
        image = image.convert("RGB")
        image.thumbnail((max_side, max_side))
        output = BytesIO()
        image.save(output, format="JPEG", quality=82, optimize=True)
    return output.getvalue()
