import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from .src.routers import events, transcription
from .src.config import settings
from .otel import init_tracing

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Shared HTTP client (used for local-dev publish)
    httpx_client = httpx.AsyncClient(timeout=10.0, http2=True)
    app.state.httpx_client = httpx_client

    # Optionally warm the model to reduce first-request latency:
    from .src.service import load_model_once
    load_model_once()

    try:
        yield
    finally:
        await httpx_client.aclose()

app = FastAPI(title="Transcription Service API", version="1.2.0", lifespan=lifespan)

# Routers
app.include_router(transcription.router, prefix="/api/v1")
app.include_router(events.router)

os.environ.setdefault("SERVICE_NAME", settings.service_name)
tracer = init_tracing(app, service_name=settings.service_name, service_version="v1")

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.service_name}