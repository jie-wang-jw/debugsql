from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.craigslist.registry import craigslist_root, load_furniture, load_images
from app.semantic_index.store import craigslist_index_dir, load_index, load_manifest


def build_craigslist_indexes() -> dict:
    import numpy as np
    import open_clip
    import torch
    from PIL import Image
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    output = craigslist_index_dir()
    output.mkdir(parents=True, exist_ok=True)
    expected_image_model = f"{settings.clip_model}/{settings.clip_pretrained}"
    previous = load_manifest()
    previous_images = _previous_vectors("image", previous.get("imageModel") == expected_image_model)
    previous_titles = _previous_vectors("title", previous.get("textModel") == settings.text_embedding_model)
    previous_image_checksums = previous.get("imageChecksums", {})
    previous_title_checksums = previous.get("titleChecksums", {})

    image_rows: list[tuple[str, Path, str]] = []
    checksums: dict[str, str] = {}
    failed: list[dict[str, str]] = []
    reused_images = 0
    image_vectors: dict[str, object] = {}

    for row in load_images():
        image_id = row["img"]
        path = craigslist_root() / "furniture_imgs" / Path(image_id).name
        try:
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            failed.append({"id": image_id, "error": str(exc)})
            continue
        checksums[image_id] = checksum
        if previous_image_checksums.get(image_id) == checksum and image_id in previous_images:
            image_vectors[image_id] = previous_images[image_id]
            reused_images += 1
        else:
            image_rows.append((image_id, path, checksum))

    model = preprocess = tokenizer = None
    if image_rows:
        model, _, preprocess = open_clip.create_model_and_transforms(
            settings.clip_model, pretrained=settings.clip_pretrained
        )
        tokenizer = open_clip.get_tokenizer(settings.clip_model)
        model.eval()

    batch_images: list = []
    batch_ids: list[str] = []

    def flush() -> None:
        if not batch_images:
            return
        with torch.no_grad():
            encoded = model.encode_image(torch.stack(batch_images))
            encoded /= encoded.norm(dim=-1, keepdim=True)
        for image_id, vector in zip(batch_ids, encoded.cpu().numpy(), strict=True):
            image_vectors[image_id] = vector
        batch_images.clear()
        batch_ids.clear()

    for image_id, path, _ in image_rows:
        try:
            with Image.open(path) as image:
                batch_images.append(preprocess(image.convert("RGB")))
            batch_ids.append(image_id)
            if len(batch_images) >= 32:
                flush()
        except Exception as exc:  # corrupt benchmark files are reported, not fatal
            failed.append({"id": image_id, "error": str(exc)})
    flush()
    ids = [row["img"] for row in load_images() if row["img"] in image_vectors]
    vectors = np.asarray([image_vectors[image_id] for image_id in ids], dtype="float32")
    np.save(output / "image_embeddings.npy", vectors)
    (output / "image_ids.json").write_text(json.dumps(ids), encoding="utf-8")

    title_rows = [(row["aid"], str(row.get("title") or "")) for row in load_furniture()]
    title_checksums = {
        aid: hashlib.sha256(title.encode("utf-8")).hexdigest() for aid, title in title_rows
    }
    title_vectors_by_id = {
        aid: previous_titles[aid]
        for aid, _ in title_rows
        if aid in previous_titles and previous_title_checksums.get(aid) == title_checksums[aid]
    }
    changed_titles = [(aid, title) for aid, title in title_rows if aid not in title_vectors_by_id]
    if changed_titles:
        title_model = SentenceTransformer(settings.text_embedding_model)
        encoded_titles = title_model.encode(
            [title for _, title in changed_titles], normalize_embeddings=True, show_progress_bar=True
        )
        title_vectors_by_id.update({
            aid: vector for (aid, _), vector in zip(changed_titles, encoded_titles, strict=True)
        })
    title_vectors = np.asarray(
        [title_vectors_by_id[aid] for aid, _ in title_rows], dtype="float32"
    )
    np.save(output / "title_embeddings.npy", title_vectors)
    (output / "title_ids.json").write_text(
        json.dumps([aid for aid, _ in title_rows]), encoding="utf-8"
    )

    # Validate the paired CLIP text encoder when the model was loaded.
    if model is not None and tokenizer is not None:
        with torch.no_grad():
            model.encode_text(tokenizer(["index validation"])).cpu()
    manifest = {
        "benchmark": "craigslist",
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "imageModel": expected_image_model,
        "textModel": settings.text_embedding_model,
        "indexedImageCount": len(ids),
        "indexedTitleCount": len(title_rows),
        "failedCount": len(failed),
        "failed": failed,
        "processedImageCount": len(image_vectors) - reused_images,
        "reusedImageCount": reused_images,
        "processedTitleCount": len(changed_titles),
        "reusedTitleCount": len(title_rows) - len(changed_titles),
        "imageChecksums": checksums,
        "titleChecksums": title_checksums,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cache_clear = getattr(load_index, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
    return manifest


def _previous_vectors(kind: str, compatible: bool) -> dict[str, object]:
    if not compatible:
        return {}
    try:
        index = load_index(kind)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return {}
    vectors = {
        item_id: index.vectors[position].copy()
        for position, item_id in enumerate(index.ids)
    }
    # Release the NumPy mmap before replacing the same .npy file on Windows.
    del index
    cache_clear = getattr(load_index, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
    return vectors
