from fastapi import FastAPI
from .routers import campaigns

app = FastAPI(title="CTV Ad Analytics API", version="1.0.0")
app.include_router(campaigns.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
