from __future__ import annotations

from typing import Any, Protocol

from app.benchmarks.descriptor import BenchmarkDescriptor


class BenchmarkProvider(Protocol):
    """Metadata provider for one benchmark family.

    Execution stays with the connector layer; providers only supply
    descriptors and database listings.
    """

    def descriptors(self) -> list[BenchmarkDescriptor]: ...

    def list_databases(self, benchmark_id: str) -> list[dict[str, Any]]: ...


class RelationalBenchmarkProvider:
    """Wraps the existing Spider/BIRD registry (app.benchmark_registry)."""

    _DESCRIPTIONS = {
        "spider": "Cross-domain text-to-SQL benchmark over relational SQLite databases.",
        "bird": "Large-scale text-to-SQL benchmark with realistic, noisy relational databases.",
    }

    def descriptors(self) -> list[BenchmarkDescriptor]:
        from app.benchmark_registry import list_benchmarks

        return [
            BenchmarkDescriptor(
                id=item["id"],
                label=item["label"],
                status=item["status"],
                connector="sqlite_benchmark",
                modalities=["table"],
                capabilities=["structured_sql", "cross_table_join"],
                databaseCount=item.get("databaseCount", 0),
                description=self._DESCRIPTIONS.get(item["id"], ""),
            )
            for item in list_benchmarks()
        ]

    def list_databases(self, benchmark_id: str) -> list[dict[str, Any]]:
        from app.benchmark_registry import list_databases

        return list_databases(benchmark_id)


class MultimodalBenchmarkProvider:
    """Wraps the multimodal demo dataset registry (app.multimodal.registry)."""

    def descriptors(self) -> list[BenchmarkDescriptor]:
        from app.multimodal.registry import dataset_info

        info = dataset_info()
        return [
            BenchmarkDescriptor(
                id=info["id"],
                label=info["label"],
                status=info["status"],
                connector="multimodal_demo",
                modalities=["table", "image", "audio", "video"],
                capabilities=[
                    "structured_sql",
                    "cross_table_join",
                    "image_semantic_predicate",
                    "audio_semantic_predicate",
                    "video_semantic_predicate",
                    "ai_fuzzy_match",
                ],
                databaseCount=1,
                description=(
                    "Prepared multimodal demo (ThalamusDB car samples plus image/audio/video "
                    "assets) supporting NL_FILTER semantic predicates."
                ),
                extra={
                    "entityCount": info.get("entityCount", 0),
                    "mediaCounts": info.get("mediaCounts", {}),
                },
            )
        ]
    def list_databases(self, benchmark_id: str) -> list[dict[str, Any]]:
        from app.multimodal.registry import dataset_info

        info = dataset_info()
        return [
            {
                "benchmark": info["id"],
                "dbId": info["id"],
                "label": info["label"],
                "hasSQLite": info["status"] == "ready",
                "tableCount": 2,
                "sampleQuestions": [],
            }
        ]
class CraigslistBenchmarkProvider:
    """Descriptor for the prepared Craigslist furniture/image benchmark."""

    def descriptors(self) -> list[BenchmarkDescriptor]:
        from app.craigslist.registry import dataset_info

        info = dataset_info()
        return [
            BenchmarkDescriptor(
                id="craigslist",
                label="Craigslist Furniture",
                status=info["status"],
                connector="craigslist",
                modalities=["table", "text", "image"],
                capabilities=[
                    "structured_sql",
                    "cross_table_join",
                    "image_semantic_predicate",
                    "ai_fuzzy_match",
                ],
                databaseCount=1,
                description=(
                    "Craigslist furniture listings joined with prepared listing images. "
                    "Natural-language predicates compile to NL_FILTER semantic SQL."
                ),
                extra={
                    "listingCount": info["listingCount"],
                    "mediaCounts": {"image": info["imageCount"]},
                    "indexStatus": info.get("indexStatus", "missing"),
                    "imageModel": info.get("imageModel", ""),
                    "imageCount": info.get("imageCount", 0),
                    "indexedImageCount": info.get("indexedImageCount", 0),
                    "visionReranker": info.get("visionReranker", ""),
                },
            )
        ]

    def list_databases(self, benchmark_id: str) -> list[dict[str, Any]]:
        from app.craigslist.registry import dataset_info

        info = dataset_info()
        return [
            {
                "benchmark": "craigslist",
                "dbId": "craigslist",
                "label": "Craigslist Furniture",
                "hasSQLite": info["status"] == "ready",
                "tableCount": 2,
                "sampleQuestions": [
                    {"question": "Show blue chair images under 200 dollars"},
                    {"question": "Find wooden tables with matching photos"},
                    {"question": "Show red furniture images sorted by price"},
                ],
            }
        ]

