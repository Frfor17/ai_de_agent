from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel
import asyncpg
from typing import Any, Dict, List
import os
import socket
from contextlib import closing
from typing import Optional

# Optional LangGraph/LLM imports
try:
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict
    from langchain_openai import ChatOpenAI
except Exception:  # noqa: BLE001
    StateGraph = None  # type: ignore
    START = None  # type: ignore
    END = None  # type: ignore
    ChatOpenAI = None  # type: ignore


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


class DbRequest(BaseModel):
    url: str
    query: str | None = None


@app.post("/api/db/test")
async def db_test(req: DbRequest) -> JSONResponse:
    if not req.url:
        raise HTTPException(status_code=400, detail="Missing 'url'")

    query = req.query or "SELECT 1 AS ok"

    try:
        conn = await asyncpg.connect(req.url)
    except Exception as connect_error:  # noqa: BLE001 broad but user-facing
        raise HTTPException(status_code=400, detail=f"Connection error: {connect_error}")

    try:
        # Very basic branching for SELECT vs other
        if query.strip().lower().startswith("select"):
            rows = await conn.fetch(query)
            serialized: List[Dict[str, Any]] = [dict(r) for r in rows]
            return JSONResponse({"ok": True, "rows": serialized, "rowCount": len(serialized)})
        else:
            status = await conn.execute(query)  # e.g. 'INSERT 0 1'
            return JSONResponse({"ok": True, "status": status})
    except Exception as query_error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Query error: {query_error}")
    finally:
        try:
            await conn.close()
        except Exception:
            pass


def _is_port_open(host: str, port: int, timeout_seconds: float = 0.25) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout_seconds)
        try:
            return sock.connect_ex((host, port)) == 0
        except Exception:
            return False


@app.get("/api/db/discover")
def db_discover() -> JSONResponse:
    env_url = os.getenv("DATABASE_URL")
    hosts = ["127.0.0.1", "localhost"]
    ports = [5432, 5433, 5434, 5435]
    open_endpoints: List[Dict[str, Any]] = []

    for host in hosts:
        for port in ports:
            if _is_port_open(host, port):
                open_endpoints.append({"host": host, "port": port})

    # Build simple suggestions (credentials required from user)
    suggestions = [
        f"postgres://user:pass@{e['host']}:{e['port']}/postgres" for e in open_endpoints
    ]

    return JSONResponse(
        {
            "ok": True,
            "envUrl": env_url,
            "open": open_endpoints,
            "suggestedUrls": suggestions,
            "note": "Открытые порты найдены. Укажи свои user/pass/db в URL.",
        }
    )


class ChatMessage(BaseModel):
    message: str


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph
    if StateGraph is None or ChatOpenAI is None:
        return None

    class ChatState(TypedDict):
        input: str
        output: str

    def llm_node(state: ChatState) -> ChatState:
        # Prefer OpenRouter if configured; otherwise fallback to OpenAI
        or_api_key = os.getenv("OPENROUTER_API_KEY")
        or_model = os.getenv("OPENROUTER_MODEL")
        or_base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api")

        if or_api_key:
            model_name = or_model or "x-ai/grok-4-fast:free"
            # Optional headers recommended by OpenRouter
            extra_headers = {}
            referer = os.getenv("OPENROUTER_HTTP_REFERER")
            if referer:
                extra_headers["HTTP-Referer"] = referer
            site_title = os.getenv("OPENROUTER_X_TITLE")
            if site_title:
                extra_headers["X-Title"] = site_title
            llm = ChatOpenAI(model=model_name, api_key=or_api_key, base_url=or_base, default_headers=extra_headers or None)
        else:
            model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Without any API key, fallback later
                raise RuntimeError("Missing OPENROUTER_API_KEY or OPENAI_API_KEY")
            llm = ChatOpenAI(model=model_name, api_key=api_key)
        resp = llm.invoke(state["input"])  # type: ignore[arg-type]
        return {"input": state["input"], "output": resp.content}

    graph = StateGraph(ChatState)
    graph.add_node("llm", llm_node)
    graph.add_edge(START, "llm")
    graph.add_edge("llm", END)
    _compiled_graph = graph.compile()
    return _compiled_graph


@app.post("/api/chat")
def chat(msg: ChatMessage) -> JSONResponse:
    text = (msg.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message")
    graph = _get_graph()
    if graph is None:
        # Fallback stub if LangGraph not configured
        return JSONResponse({
            "reply": "Заглушка: я получил ваше сообщение.",
            "echo": text,
        })
    try:
        result = graph.invoke({"input": text})
        output = result.get("output") if isinstance(result, dict) else None
        return JSONResponse({"reply": output or "(пусто)", "echo": text})
    except Exception as e:  # noqa: BLE001
        # On any error (e.g., missing API key) use stub
        return JSONResponse({
            "reply": f"Заглушка (ошибка LLM: {e})",
            "echo": text,
        })


if __name__ == "__main__":
    # For local debugging: python app/app.py
    import uvicorn

    uvicorn.run("app.app:app", host="0.0.0.0", port=8000, reload=True)


