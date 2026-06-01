from __future__ import annotations

from app.config import get_settings
from app.nl2ir.kddcup_provider import KDDCupTraceNL2IRProvider
from app.nl2ir.schemas import NL2IRRequest, NL2IRResult
from app.nl2ir.stub_provider import StubNL2IRProvider


class NL2IRProvider:
    def generate_ir(self, request: NL2IRRequest) -> NL2IRResult | None:
        raise NotImplementedError


def get_nl2ir_provider() -> NL2IRProvider:
    settings = get_settings()
    provider_name = settings.nl2ir_provider.lower()

    if provider_name == "stub":
        return StubNL2IRProvider()
    if provider_name == "kddcup":
        return KDDCupTraceNL2IRProvider()

    raise ValueError(f"Unsupported NL-to-IR provider: {settings.nl2ir_provider}")

