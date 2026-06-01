from __future__ import annotations

from app.nl2ir.schemas import NL2IRRequest, NL2IRResult


class StubNL2IRProvider:
    """No-op provider that leaves the existing DebugSQL demo fallback in control."""

    provider_name = "stub"

    def generate_ir(self, request: NL2IRRequest) -> NL2IRResult | None:
        del request
        return None

