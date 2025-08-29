from fastapi import FastAPI
from .src.routers import redact

app = FastAPI(title="Privacy Service API", version="1.1.0")
app.include_router(redact.router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok"}