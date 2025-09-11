from fastapi import FastAPI
from .src.routers import soap_note
import os

from .otel import init_tracing

app = FastAPI(title="Soap Note API", version="1.1.0")
app.include_router(soap_note.router, prefix="/api/v1")

os.environ.setdefault("SERVICE_NAME", "soap-service")
tracer = init_tracing(app, service_name="soap-service", service_version="v1")

@app.get("/health")
def health():
    return {"status": "ok"}