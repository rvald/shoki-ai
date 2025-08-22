from fastapi import FastAPI
from .src.routers import transcription

app = FastAPI(title="Transcription Service API", version="1.0.0")
app.include_router(transcription.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)