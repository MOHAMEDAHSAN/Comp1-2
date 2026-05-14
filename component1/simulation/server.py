"""
server.py — Real-Time Kubernetes Monitoring Server
Reads live data from your Kubernetes cluster via the Python kubernetes client.
Requires: kubectl configured + Docker Desktop Kubernetes enabled.
Run:  python server.py
Open: http://localhost:8000
"""
import asyncio, json, os, sys, datetime
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from k8s_ingestor import K8sIngestor

# ── Config ────────────────────────────────────────────────────────────────────
TICK_INTERVAL_S  = 5          # poll K8s every 5 seconds
K8S_NAMESPACE    = ""         # empty string = all namespaces
DATA_DIR         = Path(os.path.dirname(__file__)) / "data"

# ── Shared state ──────────────────────────────────────────────────────────────
_k8s: K8sIngestor = None
_latest_obs: dict  = {}
_obs_history: list = []
_MAX_HISTORY       = 120
_last_save_path    = ""
_total_saved       = 0
_tick              = 0
_status            = "connecting"   # connecting | live | error


# ── Main poll loop ────────────────────────────────────────────────────────────
async def _poll_loop():
    global _latest_obs, _obs_history, _tick, _status, _last_save_path, _total_saved

    while True:
        try:
            if not _k8s.is_ready:
                # Retry connection every tick
                _k8s.__init__(namespace=K8S_NAMESPACE)
                _status = "connecting"
            else:
                obs = _k8s.collect()
                if obs:
                    obs["_tick"] = _tick
                    _latest_obs = obs
                    _obs_history.append(obs)
                    if len(_obs_history) > _MAX_HISTORY:
                        _obs_history.pop(0)
                    _tick  += 1
                    _status = "live"
                    # Auto-save every 20 ticks (~100s)
                    if _tick % 20 == 0:
                        _auto_save()
                else:
                    _status = "error"
        except Exception as exc:
            _status = "error"
            print(f"[k8s] poll error: {exc}", flush=True)

        await asyncio.sleep(TICK_INTERVAL_S)


# ── Auto-save ─────────────────────────────────────────────────────────────────
def _auto_save():
    global _last_save_path, _total_saved
    DATA_DIR.mkdir(exist_ok=True)
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"k8s_live_{ts}.ndjson"
    with open(path, "w", encoding="utf-8") as f:
        for obs in _obs_history:
            f.write(json.dumps(obs, default=str) + "\n")
    _last_save_path = str(path)
    _total_saved   += len(_obs_history)
    print(f"[k8s] saved {len(_obs_history)} obs -> {path.name}", flush=True)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application):
    global _k8s
    print("[k8s] Connecting to Kubernetes...", flush=True)
    _k8s = K8sIngestor(namespace=K8S_NAMESPACE)
    if _k8s.is_ready:
        print("[k8s] OK  Live -- streaming real cluster data", flush=True)
    else:
        print("[k8s] OFFLINE -- Enable Kubernetes in Docker Desktop.", flush=True)
        print("[k8s]   Settings -> Kubernetes -> Enable Kubernetes -> Apply & Restart", flush=True)
    asyncio.create_task(_poll_loop())
    print("[k8s] Dashboard -> http://localhost:8000", flush=True)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="K8s Live Monitor", lifespan=lifespan)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html", status_code=302)

@app.get("/api/state")
async def get_state():
    return _latest_obs or {"_status": _status, "_connected": _k8s.is_ready if _k8s else False}

@app.get("/api/history")
async def get_history():
    return _obs_history

@app.get("/api/status")
async def get_status():
    return {
        "status":    _status,
        "connected": _k8s.is_ready if _k8s else False,
        "namespace": K8S_NAMESPACE,
        "tick":      _tick,
        "obs_count": len(_obs_history),
    }

@app.get("/api/save-status")
async def save_status():
    files = sorted(DATA_DIR.glob("*.ndjson")) if DATA_DIR.exists() else []
    return {
        "last_file":   _last_save_path,
        "total_saved": _total_saved,
        "file_count":  len(files),
        "files":       [{"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)} for f in files[-5:]],
    }

@app.post("/api/save-now")
async def save_now():
    _auto_save()
    return {"saved": _last_save_path, "obs_count": len(_obs_history)}

@app.get("/api/stream")
async def stream():
    async def gen():
        last = -1
        while True:
            t = _latest_obs.get("_tick", -1)
            if t != last and _latest_obs:
                last = t
                yield f"data: {json.dumps(_latest_obs, default=str)}\n\n"
            elif not _latest_obs:
                # Send status heartbeat so dashboard knows we're trying
                yield f"data: {json.dumps({'_status': _status, '_connected': _k8s.is_ready if _k8s else False})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
