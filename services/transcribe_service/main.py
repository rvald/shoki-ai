from fastapi import FastAPI
from .src.routers import transcription, events
import os

from .otel import init_tracing

app = FastAPI(title="Transcription Service API", version="1.1.0")
app.include_router(transcription.router, prefix="/api/v1")
app.include_router(events.router) 

os.environ.setdefault("SERVICE_NAME", "transcribe-service")
tracer = init_tracing(app, service_name="transcribe-service", service_version="v1")

@app.get("/health")
def health():
    return {"status": "ok"}