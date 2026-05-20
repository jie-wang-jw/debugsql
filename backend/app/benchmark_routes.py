from fastapi import APIRouter

from app.benchmark_registry import list_benchmarks, list_databases


router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.get("")
def benchmarks() -> dict:
    return {"success": True, "data": list_benchmarks()}


@router.get("/{benchmark}/databases")
def benchmark_databases(benchmark: str) -> dict:
    return {"success": True, "data": list_databases(benchmark)}
