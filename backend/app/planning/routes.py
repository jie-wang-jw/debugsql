from fastapi import APIRouter, HTTPException

from app.planning.provider import get_ir_to_plan_provider
from app.planning.schemas import PlanningRequest, PlanningResponse


router = APIRouter(prefix="/planning", tags=["planning"])


@router.post("/generate", response_model=PlanningResponse)
def generate_plan(request: PlanningRequest) -> PlanningResponse:
    provider = get_ir_to_plan_provider()
    try:
        plan = provider.generate_plan(request)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return PlanningResponse(plan=plan)
