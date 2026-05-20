from app.planning.schemas import PlanningRequest, QueryPlan


class InternalIRToPlanProvider:
    """Placeholder for a future in-process planner package or algorithm module."""

    provider_name = "internal"

    def generate_plan(self, request: PlanningRequest) -> QueryPlan:
        raise NotImplementedError(
            "Internal IR-to-plan provider is reserved for a future Python planner package."
        )
