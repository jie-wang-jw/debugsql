from app.planning.schemas import PlanningRequest, QueryPlan


class HTTPIRToPlanProvider:
    """Placeholder for the external IR-to-plan service owned by another team."""

    provider_name = "http"

    def __init__(self, api_url: str, api_key: str = "", timeout_seconds: int = 30) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate_plan(self, request: PlanningRequest) -> QueryPlan:
        raise NotImplementedError(
            "HTTP IR-to-plan provider is reserved for the external planning API."
        )
