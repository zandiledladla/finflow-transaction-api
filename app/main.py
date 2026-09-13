import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401
from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Alembic migrations will replace this bootstrap step in the next milestone.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A tested transaction-processing API for customers, accounts and transfers.",
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")
static_directory = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_directory), name="static")


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started_at = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    logging.getLogger("finflow.requests").info(
        "request_completed method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/", tags=["service"])
def service_information() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "documentation": "/docs",
        "health": "/health",
        "demo": "/demo",
    }


@app.get("/demo", include_in_schema=False)
def interactive_demo() -> FileResponse:
    return FileResponse(static_directory / "index.html")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "healthy", "version": settings.app_version}
