from fastapi import FastAPI
from .src.routers import audit, events

import os
from .otel import init_tracing

app = FastAPI(title="Compliance API", version="1.1.0")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(events.router)

os.environ.setdefault("SERVICE_NAME", "compliance-service")
tracer = init_tracing(app, service_name="compliance-service", service_version="v1")

@app.get("/health")
def health():
    return {"status": "ok"}