from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api import tasks, calls, devices, recordings

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="有证慧催 API",
    version="0.1.0",
    description="autoluyin MVP backend",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(recordings.router, prefix="/api/recordings", tags=["recordings"])


@app.get("/health")
def health():
    return {"status": "ok"}
