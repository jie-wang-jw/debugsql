from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    debugsql_auto_login: bool = True
    debugsql_dev_user_email: str = "dev@debugsql.local"
    debugsql_dev_user_name: str = "DebugSQL Dev User"
    nl2ir_provider: str = "stub"
    ir_to_plan_provider: str = "stub"
    ir_to_plan_api_url: str = ""
    ir_to_plan_api_key: str = ""
    ir_to_plan_timeout_seconds: int = 30
    benchmark_data_dir: str = "data/benchmarks"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_cors_origins() -> list[str]:
    settings = get_settings()
    return [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
