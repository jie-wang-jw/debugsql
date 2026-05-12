from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_origins, get_settings
from app.database import check_database


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "debugsql-backend",
        "nl2ir_provider": settings.nl2ir_provider,
    }


@app.get("/db-health")
def db_health() -> dict:
    return check_database()


@app.get("/hello")
def hello() -> dict:
    return {"message": "Hello from DebugSQL backend"}
