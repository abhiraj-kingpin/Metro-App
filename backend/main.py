# run with: uvicorn main:app --reload
# then hit http://127.0.0.1:8000/ for the UI, /docs for the raw API

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router

app = FastAPI(
    title="Delhi Metro Navigator Pro - API",
    description=(
        "Lean MVP: Dijkstra-based shortest-path route finding over a real "
        "Delhi Metro network topology (7 lines). See docs/ROADMAP.md for "
        "what's stubbed vs. built."
    ),
    version="0.1.0",
)
app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# mounted last so it doesn't shadow the routes above -- this is just the
# static frontend (index.html/app.js/style.css), no templating involved
app.mount("/", StaticFiles(directory="static", html=True), name="static")
