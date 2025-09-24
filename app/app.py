from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="App")

# Serve the static directory (for assets if needed)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def read_root() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Front not found</h1>", status_code=404)


@app.get("/api/ping")
def ping() -> dict:
    return {"status": "ok"}


if __name__ == "__main__":
    # For local debugging: python app/app.py
    import uvicorn

    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=True)


