from fastapi import APIRouter

from app.benchmarks.registry import all_descriptors, list_databases


router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("")
def benchmarks() -> dict:
    return {"success": True, "data": [descriptor.model_dump() for descriptor in all_descriptors()]}


@router.get("/{benchmark}/databases")
def benchmark_databases(benchmark: str) -> dict:
    return {"success": True, "data": list_databases(benchmark)}
