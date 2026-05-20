from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_cors_origins, get_settings
from app.database import check_database
from app.chat_routes import router as chat_router
from app.execution_routes import router as execution_router
from app.planning.routes import router as planning_router
from app.query_plan_routes import router as query_plan_router


settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(planning_router)
app.include_router(chat_router)
app.include_router(query_plan_router)
app.include_router(execution_router)


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
