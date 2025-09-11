from fastapi import FastAPI
from .src.routers import redact, events
import os
from .otel import init_tracing

app = FastAPI(title="Privacy Service API", version="1.1.0")
app.include_router(redact.router, prefix="/api/v1")
app.include_router(events.router) 

os.environ.setdefault("SERVICE_NAME", "privacy-service")
tracer = init_tracing(app, service_name="privacy-service", service_version="v1")

@app.get("/health")
def health():
    return {"status": "ok"}