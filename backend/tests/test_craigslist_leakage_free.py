from __future__ import annotations

import inspect
import json
import sys
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import get_settings
from app.craigslist import registry
from app.craigslist import resolver
from app.craigslist.vision import VisionProviderError, VisionReranker
from app.evaluation.craigslist import retrieval_metrics, split_for_id
from app.semantic_index.store import VectorIndex


def test_runtime_registry_does_not_reference_evaluation_labels() -> None:
    source = inspect.getsource(registry) + inspect.getsource(resolver)
    assert "craigslist_imgs_label" not in source
    assert "craigslist_furnitures_title_label" not in source


def test_dataset_readiness_does_not_require_annotations(monkeypatch, tmp_path) -> None:
    root = tmp_path / "Craigslist"
    root.mkdir()
    (root / "furnitures.csv").write_text("aid,title,price\n1,Chair,10\n", encoding="utf-8")
    (root / "imgs.csv").write_text("img,aid\na.jpg,1\n", encoding="utf-8")
    (root / "furniture_imgs").mkdir()
    monkeypatch.setattr(registry, "craigslist_root", lambda: root)
    assert registry.dataset_ready()


def test_preview_authorization_uses_imgs_csv(monkeypatch) -> None:
    registry.image_to_aid.cache_clear()
    monkeypatch.setattr(registry, "load_images", lambda: [{"img": "raw.jpg", "aid": "1"}])
    monkeypatch.setattr(registry, "furniture_by_aid", lambda: {"1": {"title": "Original title"}})
    preview = registry.media_preview("raw.jpg", 0.7)
    assert preview and preview["caption"] == "Original title"
    assert registry.media_preview("hidden-label-only.jpg") is None
    registry.image_to_aid.cache_clear()


def test_vision_reranker_rejects_missing_ids(monkeypatch, tmp_path) -> None:
    class Message:
        content = json.dumps({"scores": [{"id": "one.jpg", "score": 0.8}]})

    class Completion:
        choices = [type("Choice", (), {"message": Message()})]

    class Completions:
        def create(self, **kwargs):
            assert any(
                item.get("type") == "image_url" and item["image_url"]["url"].startswith("data:image/")
                for item in kwargs["messages"][0]["content"]
            )
            return Completion()

    class Client:
        chat = type("Chat", (), {"completions": Completions()})()

    image_path = tmp_path / "raw.jpg"
    Image.new("RGB", (1200, 600), color="blue").save(image_path, format="JPEG")
    monkeypatch.setattr("app.craigslist.vision.OpenAI", lambda **kwargs: Client())
    monkeypatch.setattr("app.craigslist.vision.resolve_image_path", lambda image_id: image_path)
    with pytest.raises(VisionProviderError, match="every shortlisted"):
        VisionReranker()._request("chair", [("one.jpg", 0.5), ("two.jpg", 0.4)])


def test_vision_reranker_batches_and_caches_requests(monkeypatch, tmp_path) -> None:
    requests: list[list[str]] = []

    class Completions:
        def create(self, **kwargs):
            content = kwargs["messages"][0]["content"]
            ids = [item["text"].removeprefix("Image ID: ") for item in content if item.get("type") == "text" and item["text"].startswith("Image ID: ")]
            requests.append(ids)
            message = type("Message", (), {"content": json.dumps({
                "scores": [{"id": image_id, "score": 0.75} for image_id in ids]
            })})()
            return type("Completion", (), {"choices": [type("Choice", (), {"message": message})()]})()

    class Client:
        chat = type("Chat", (), {"completions": Completions()})()

    image_path = tmp_path / "raw.jpg"
    Image.new("RGB", (1600, 900), color="red").save(image_path, format="JPEG")
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("VISION_RERANK_COUNT", "24")
    get_settings.cache_clear()
    monkeypatch.setattr("app.craigslist.vision.OpenAI", lambda **kwargs: Client())
    monkeypatch.setattr("app.craigslist.vision.resolve_image_path", lambda image_id: image_path)
    monkeypatch.setattr("app.craigslist.vision.craigslist_index_dir", lambda: tmp_path)
    monkeypatch.setattr("app.craigslist.vision.load_manifest", lambda: {"imageChecksums": {}})

    reranker = VisionReranker()
    candidates = [(f"image-{index}.jpg", 0.5) for index in range(10)]
    assert len(reranker.rerank("red chair", candidates)) == 10
    assert [len(batch) for batch in requests] == [8, 2]
    assert reranker.request_count == 2
    assert reranker.scored_image_count == 10

    assert len(reranker.rerank("red chair", candidates)) == 10
    assert len(requests) == 2
    get_settings.cache_clear()


def test_index_builder_reads_real_jpeg_and_reuses_unchanged_vectors(monkeypatch, tmp_path) -> None:
    import numpy as np
    from app.semantic_index import builder

    raw_root = tmp_path / "Craigslist"
    image_root = raw_root / "furniture_imgs"
    image_root.mkdir(parents=True)
    image_path = image_root / "one.jpg"
    Image.new("RGB", (20, 10), color="green").save(image_path, format="JPEG")
    output = tmp_path / "indexes" / "craigslist"
    model_loads = 0

    class Tensor:
        def __init__(self, values):
            self.values = np.asarray(values, dtype="float32")

        def norm(self, dim=-1, keepdim=True):
            return Tensor(np.linalg.norm(self.values, axis=dim, keepdims=keepdim))

        def __itruediv__(self, other):
            self.values /= other.values
            return self

        def cpu(self):
            return self

        def numpy(self):
            return self.values

    class Model:
        def eval(self):
            return None

        def encode_image(self, values):
            return Tensor([[1.0, 2.0] for _ in values])

        def encode_text(self, values):
            return Tensor([[1.0, 1.0] for _ in values])

    def create_model(*args, **kwargs):
        nonlocal model_loads
        model_loads += 1
        return Model(), None, lambda image: np.asarray(image).mean(axis=(0, 1))[:2]

    class TitleModel:
        def __init__(self, name):
            self.name = name

        def encode(self, values, **kwargs):
            return np.asarray([[1.0, 0.0] for _ in values], dtype="float32")

    monkeypatch.setitem(sys.modules, "open_clip", SimpleNamespace(
        create_model_and_transforms=create_model,
        get_tokenizer=lambda name: lambda values: values,
    ))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        no_grad=nullcontext,
        stack=lambda values: values,
    ))
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(
        SentenceTransformer=TitleModel,
    ))
    monkeypatch.setattr(builder, "craigslist_root", lambda: raw_root)
    monkeypatch.setattr(builder, "craigslist_index_dir", lambda: output)
    monkeypatch.setattr(builder, "load_images", lambda: [{"img": "one.jpg", "aid": "1"}])
    monkeypatch.setattr(builder, "load_furniture", lambda: [{"aid": "1", "title": "Green chair"}])
    monkeypatch.setattr(builder, "load_manifest", lambda: {})

    first = builder.build_craigslist_indexes()
    assert first["processedImageCount"] == 1
    assert first["reusedImageCount"] == 0
    assert np.load(output / "image_embeddings.npy").shape == (1, 2)

    monkeypatch.setattr(builder, "load_manifest", lambda: first)

    def existing(kind):
        return VectorIndex(
            ids=json.loads((output / f"{kind}_ids.json").read_text()),
            vectors=np.load(output / f"{kind}_embeddings.npy"),
        )

    monkeypatch.setattr(builder, "load_index", existing)
    second = builder.build_craigslist_indexes()
    assert second["processedImageCount"] == 0
    assert second["reusedImageCount"] == 1
    assert second["processedTitleCount"] == 0
    assert model_loads == 1


def test_retrieval_metrics_and_split_are_deterministic() -> None:
    assert split_for_id("asset-1") == split_for_id("asset-1")
    metrics = retrieval_metrics(["a", "x", "b"], {"a", "b"}, k=3)
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == 1.0
    assert 0 < metrics["ndcgAt3"] <= 1
