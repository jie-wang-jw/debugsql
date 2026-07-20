from functools import lru_cache
from pathlib import Path

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
    ir_to_plan_provider: str = "internal"
    ir_to_plan_api_url: str = ""
    ir_to_plan_api_key: str = ""
    ir_to_plan_timeout_seconds: int = 30
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 30
    llm_api_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: int = 30
    query_plan_provider: str = "openai_compatible"
    benchmark_data_dir: str = "data/benchmarks"
    multimodal_data_dir: str = "data/multimodal_demo"
    # Minimum fraction of predicate terms that must match for NL_FILTER
    # boolean membership (0..1). 0.6 requires more than half the terms.
    semantic_sql_score_cutoff: float = 0.6
    semantic_sql_max_matches: int = 20
    semantic_resolver: str = "clip_vlm"
    semantic_index_dir: str = "data/indexes"
    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    text_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    clip_candidate_count: int = 200
    vision_provider: str = "openai_compatible"
    vision_api_base_url: str = "https://goapi.gptnb.ai/v1"
    vision_api_key: str = ""
    vision_model: str = "gpt-4o-mini"
    vision_rerank_count: int = 24
    vision_timeout_seconds: int = 60
    vision_allow_clip_only: bool = False
    craigslist_evaluation_dir: str = "data/evaluation/craigslist"
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
