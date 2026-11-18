"""FastAPI entry point: API, WebSocket fan-out, static React build, backups."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import backups, db
from .config import BACKUP_DIR, FRONTEND_DIST, MEDIA_DIR
from .routers import admin, auth, counter, public, setup
from .ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    backups.ensure_dirs()
    manager.set_loop(asyncio.get_running_loop())
    task = asyncio.create_task(backups.backup_loop())
    yield
    task.cancel()


app = FastAPI(title="Queue System", lifespan=lifespan, docs_url=None, redoc_url=None)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(setup.router)
app.include_router(counter.router)
app.include_router(admin.router)

if MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")
else:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "hello"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


def _index():
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-store"})
    return HTMLResponse(
        "<h1>Queue System</h1><p>The frontend has not been built yet. "
        "Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, "
        "then restart the server.</p>",
        status_code=503,
    )


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "not_found"}, status_code=404)
    candidate = (FRONTEND_DIST / full_path) if full_path else None
    if candidate and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
        return FileResponse(candidate)
    return _index()


def run():
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
