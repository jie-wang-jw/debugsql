from app.config import get_settings
from app.planning.http_provider import HTTPIRToPlanProvider
from app.planning.internal_provider import InternalIRToPlanProvider
from app.planning.schemas import PlanningRequest, QueryPlan
from app.planning.stub_provider import StubIRToPlanProvider


class IRToPlanProvider:
    def generate_plan(self, request: PlanningRequest) -> QueryPlan:
        raise NotImplementedError


def get_ir_to_plan_provider() -> IRToPlanProvider:
    settings = get_settings()
    provider_name = settings.ir_to_plan_provider.lower()

    if provider_name == "stub":
        return StubIRToPlanProvider()
    if provider_name == "http":
        return HTTPIRToPlanProvider(
            api_url=settings.ir_to_plan_api_url,
            api_key=settings.ir_to_plan_api_key,
            timeout_seconds=settings.ir_to_plan_timeout_seconds,
        )
    if provider_name == "internal":
        return InternalIRToPlanProvider()

    raise ValueError(f"Unsupported IR-to-plan provider: {settings.ir_to_plan_provider}")
