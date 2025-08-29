from fastapi import FastAPI
from .src.routers import audit

app = FastAPI(title="Compliance API", version="1.1.0")
app.include_router(audit.router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok"}