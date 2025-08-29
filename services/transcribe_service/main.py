from fastapi import FastAPI
from .src.routers import transcription

app = FastAPI(title="Transcription Service API", version="1.1.0")
app.include_router(transcription.router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok"}