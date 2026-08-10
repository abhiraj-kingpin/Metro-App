# run with: uvicorn main:app --reload
# then hit http://127.0.0.1:8000/docs

from fastapi import FastAPI

from app.api.routes import router as api_router

app = FastAPI(
    title="Delhi Metro Navigator Pro - API",
    description=(
        "Lean MVP: Dijkstra-based shortest-path route finding over a real "
        "Delhi Metro network topology (5 lines). See docs/ROADMAP.md for "
        "what's stubbed vs. built."
    ),
    version="0.1.0",
)
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
