from __future__ import annotations

from typing import Any

from app.benchmarks.descriptor import BenchmarkDescriptor
from app.benchmarks.providers import (
    BenchmarkProvider,
    MultimodalBenchmarkProvider,
    RelationalBenchmarkProvider,
)

_PROVIDERS: list[BenchmarkProvider] = [
    RelationalBenchmarkProvider(),
    MultimodalBenchmarkProvider(),
]


def all_descriptors() -> list[BenchmarkDescriptor]:
    return [descriptor for provider in _PROVIDERS for descriptor in provider.descriptors()]


def find_descriptor(benchmark_id: str | None) -> BenchmarkDescriptor | None:
    if not benchmark_id:
        return None
    return next((d for d in all_descriptors() if d.id == benchmark_id), None)


def descriptor_for_context(db_type: str, benchmark: str | None) -> BenchmarkDescriptor | None:
    """Resolve the descriptor for a dataset context.

    The multimodal connector has a single dataset, so its descriptor can be
    resolved from the connector type alone.
    """
    if db_type == "multimodal_demo":
        return find_descriptor("multimodal_demo")
    if db_type == "sqlite_benchmark":
        return find_descriptor(benchmark)
    return None


def list_databases(benchmark_id: str) -> list[dict[str, Any]]:
    for provider in _PROVIDERS:
        if any(d.id == benchmark_id for d in provider.descriptors()):
            return provider.list_databases(benchmark_id)
    return []
