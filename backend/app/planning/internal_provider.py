from app.planning.schemas import PlanningRequest, QueryPlan
from app.planning.stub_provider import StubIRToPlanProvider


class InternalIRToPlanProvider:
    """In-process relational IR-to-plan planner.

    The first implementation reuses the deterministic relational planner while
    exposing the stable "internal" provider name expected by the proposal.
    """

    provider_name = "internal"

    def generate_plan(self, request: PlanningRequest) -> QueryPlan:
        plan = StubIRToPlanProvider().generate_plan(request)
        plan.metadata["provider"] = self.provider_name
        plan.metadata["planner_base"] = "stub_relational"
        return plan
