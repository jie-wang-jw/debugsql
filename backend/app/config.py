from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _discover_env_files() -> tuple[str, ...]:
    candidates = (_REPO_ROOT / ".env", _BACKEND_ROOT / ".env", Path(".env"))
    return tuple(str(path) for path in candidates if path.is_file())


class Settings(BaseSettings):
    app_name: str = "DebugSQL Backend"
    database_url: str = "postgresql+psycopg://debugsql:debugsql_dev_password@postgres:5432/debugsql"
    app_base_url: str = "http://127.0.0.1:8000"
    frontend_base_url: str = "http://127.0.0.1:5173"
    session_secret: str = "change_me_in_production"
    auth_cookie_name: str = "debugsql_session"
    auth_cookie_secure: bool = False
    email_login_code_ttl_minutes: int = 10
    email_login_resend_seconds: int = 60
    email_login_max_attempts: int = 5
    email_dev_log_codes: bool = True
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "DebugSQL <no-reply@debugsql.local>"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    debugsql_auto_login: bool = True
    debugsql_dev_user_email: str = "dev@debugsql.local"
    debugsql_dev_user_name: str = "DebugSQL Dev User"
    nl2ir_provider: str = "stub"
    kddcup_agent_model: str = "gpt-4.1-mini"
    kddcup_agent_api_base: str = "https://api.openai.com/v1"
    # LLM (OpenAI-compatible) API key for the KDDCup data-agent. Prefer
    # KDDCUP_LLM_API_KEY; KDDCUP_AGENT_API_KEY is kept as a backward-compatible alias.
    kddcup_llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("KDDCUP_LLM_API_KEY", "KDDCUP_AGENT_API_KEY"),
    )
    kddcup_agent_max_steps: int = 8
    kddcup_agent_timeout_seconds: int = 120
    kddcup_work_dir: str = "/tmp/debugsql-kddcup"
    ir_to_plan_provider: str = "internal"
    ir_to_plan_api_url: str = ""
    ir_to_plan_api_key: str = ""
    ir_to_plan_timeout_seconds: int = 30
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 30
    query_plan_provider: str = "gemini"
    benchmark_data_dir: str = "data/benchmarks"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=_discover_env_files() or (".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins() -> list[str]:
    settings = get_settings()
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
