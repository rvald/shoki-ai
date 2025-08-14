from fastapi import FastAPI
from .routers import audit

app = FastAPI(title="Compliance API", version="1.0.0")
app.include_router(audit.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)