"""
server.py — Real-Time Kubernetes Monitoring Server
Reads live data from your Kubernetes cluster via the Python kubernetes client.
Requires: kubectl configured + Docker Desktop Kubernetes enabled.
Run:  python server.py
Open: http://localhost:8000
"""
import asyncio, json, os, sys, datetime, uuid, tempfile
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
_retry_count       = 0


# ── Main poll loop ────────────────────────────────────────────────────────────
async def _poll_loop():
    global _k8s, _latest_obs, _obs_history, _tick, _status, _last_save_path, _total_saved, _retry_count

    while True:
        try:
            if not _k8s.is_ready:
                # Create a fresh ingestor instance to retry the connection
                _retry_count += 1
                _status = "connecting"
                print(f"[k8s] Retry #{_retry_count} — attempting to reconnect...", flush=True)
                _k8s = K8sIngestor(namespace=K8S_NAMESPACE)
                if _k8s.is_ready:
                    print("[k8s] Reconnected successfully!", flush=True)
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
                    _retry_count = 0  # reset on success
                    # Auto-save every 20 ticks (~100s)
                    if _tick % 20 == 0:
                        _auto_save()
                else:
                    _status = "error"
                    _k8s._ready = False  # force reconnect on next tick
        except Exception as exc:
            _status = "error"
            print(f"[k8s] poll error: {exc}", flush=True)
            _k8s._ready = False  # force reconnect on next tick

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

# ── Load Test Manager ────────────────────────────────────────────────────────
_lt_active:    dict  = None   # currently running test | None
_lt_scheduled: list  = []     # upcoming scheduled tests
_lt_history:   list  = []     # last 20 completed tests
_lt_lock:      asyncio.Lock = None  # created in lifespan

_LT_YAMLS = {
    "cpu": """apiVersion: v1
kind: Pod
metadata:
  name: loadgen-cpu
  namespace: default
  labels: {app: loadgen, type: cpu-stress}
spec:
  containers:
  - name: stress
    image: polinux/stress
    args: ["stress","--cpu","2","--timeout","9000s"]
    resources:
      requests: {cpu: "500m", memory: "64Mi"}
      limits:   {cpu: "1000m", memory: "128Mi"}
  restartPolicy: Never""",
    "mem": """apiVersion: v1
kind: Pod
metadata:
  name: loadgen-mem
  namespace: default
  labels: {app: loadgen, type: mem-stress}
spec:
  containers:
  - name: stress
    image: polinux/stress
    args: ["stress","--vm","1","--vm-bytes","256M","--vm-hang","0","--timeout","9000s"]
    resources:
      requests: {cpu: "100m", memory: "128Mi"}
      limits:   {cpu: "200m", memory: "512Mi"}
  restartPolicy: Never""",
    "crash": """apiVersion: v1
kind: Pod
metadata:
  name: loadgen-crash
  namespace: default
  labels: {app: loadgen, type: crash-loop}
spec:
  containers:
  - name: crasher
    image: busybox
    command: ["sh","-c","sleep 5; exit 1"]
    resources:
      requests: {cpu: "10m", memory: "16Mi"}
      limits:   {cpu: "50m",  memory: "32Mi"}
  restartPolicy: Always""",
}
_LT_POD_NAMES = {"cpu": "loadgen-cpu", "mem": "loadgen-mem", "crash": "loadgen-crash"}
_LT_TYPE_PODS = {
    "cpu":   ["cpu"],
    "mem":   ["mem"],
    "crash": ["crash"],
    "spike": ["cpu", "mem", "crash"],
}

async def _kubectl(*args):
    proc = await asyncio.create_subprocess_exec(
        "kubectl", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

async def _apply_lt_yaml(key: str):
    yaml_str = _LT_YAMLS[key]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str); tmp = f.name
    await _kubectl("apply", "-f", tmp)
    os.unlink(tmp)

async def _cleanup_lt_pods(keys: list):
    for k in keys:
        name = _LT_POD_NAMES.get(k)
        if name:
            await _kubectl("delete", "pod", name, "-n", "default", "--ignore-not-found")

async def _run_lt(lt: dict):
    global _lt_active, _lt_history
    pod_keys = _LT_TYPE_PODS.get(lt["type"], [])
    lt["status"] = "running"
    lt["started_at"] = datetime.datetime.now().isoformat()
    print(f"[loadtest] START id={lt['id']} type={lt['type']} dur={lt['duration_s']}s", flush=True)
    try:
        await _cleanup_lt_pods(pod_keys)
        await asyncio.sleep(1)
        for k in pod_keys:
            await _apply_lt_yaml(k)
        elapsed = 0
        while elapsed < lt["duration_s"]:
            if lt.get("cancelled"):
                break
            await asyncio.sleep(1)
            elapsed += 1
            lt["elapsed_s"] = elapsed
    except Exception as e:
        lt["error"] = str(e)
    finally:
        await _cleanup_lt_pods(pod_keys)
        lt["ended_at"] = datetime.datetime.now().isoformat()
        lt["status"] = "cancelled" if lt.get("cancelled") else "completed"
        print(f"[loadtest] {lt['status'].upper()} id={lt['id']}", flush=True)
        async with _lt_lock:
            _lt_active = None
            _lt_history.insert(0, dict(lt))
            if len(_lt_history) > 20:
                _lt_history.pop()

async def _lt_scheduler_loop():
    global _lt_active, _lt_scheduled
    while True:
        await asyncio.sleep(10)
        if _lt_lock is None:
            continue
        async with _lt_lock:
            if _lt_active is not None:
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            for i, s in enumerate(_lt_scheduled):
                start = datetime.datetime.fromisoformat(s["start_iso"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=datetime.timezone.utc)
                if now >= start:
                    _lt_scheduled.pop(i)
                    # Re-queue if repeating
                    rep = s.get("repeat_s")
                    rep_end = s.get("repeat_end_iso")
                    if rep and rep_end:
                        end_dt = datetime.datetime.fromisoformat(rep_end)
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
                        next_s = start + datetime.timedelta(seconds=rep)
                        if next_s <= end_dt:
                            _lt_scheduled.append({**s, "start_iso": next_s.isoformat()})
                    lt = {"id": s["id"], "type": s["type"],
                          "duration_s": s["duration_s"], "label": s.get("label", ""),
                          "status": "starting", "elapsed_s": 0}
                    _lt_active = lt
                    asyncio.create_task(_run_lt(lt))
                    break


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(application):
    global _k8s, _lt_lock
    print("[k8s] Connecting to Kubernetes...", flush=True)
    _k8s = K8sIngestor(namespace=K8S_NAMESPACE)
    if _k8s.is_ready:
        print("[k8s] OK  Live -- streaming real cluster data", flush=True)
    else:
        print("[k8s] OFFLINE -- Enable Kubernetes in Docker Desktop.", flush=True)
        print("[k8s]   Settings -> Kubernetes -> Enable Kubernetes -> Apply & Restart", flush=True)
    _lt_lock = asyncio.Lock()
    asyncio.create_task(_poll_loop())
    asyncio.create_task(_lt_scheduler_loop())
    print("[k8s] Dashboard -> http://localhost:8000", flush=True)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="K8s Live Monitor", lifespan=lifespan)
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)  # ensure static dir exists
app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html", status_code=302)

@app.get("/index.html")
async def index_html():
    """Fallback direct route for the dashboard HTML file."""
    html_path = static_dir / "index.html"
    if html_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(str(html_path), media_type="text/html")
    return JSONResponse({"detail": "index.html not found in static dir", "static_dir": str(static_dir)}, status_code=404)

@app.get("/api/state")
async def get_state():
    return _latest_obs or {"_status": _status, "_connected": _k8s.is_ready if _k8s else False}

@app.get("/api/history")
async def get_history():
    return _obs_history

@app.get("/api/status")
async def get_status():
    return {
        "status":      _status,
        "connected":   _k8s.is_ready if _k8s else False,
        "namespace":   K8S_NAMESPACE,
        "tick":        _tick,
        "obs_count":   len(_obs_history),
        "retry_count": _retry_count,
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
                yield f"data: {json.dumps({'_status': _status, '_connected': _k8s.is_ready if _k8s else False, '_retry': _retry_count})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Load Test API ─────────────────────────────────────────────────────────────
@app.get("/api/loadtest/status")
async def lt_status():
    return {"active": _lt_active, "scheduled": _lt_scheduled, "history": _lt_history[:10]}

@app.post("/api/loadtest/run")
async def lt_run(body: dict):
    global _lt_active
    async with _lt_lock:
        if _lt_active is not None:
            return JSONResponse({"error": "A test is already running"}, status_code=409)
        lt = {"id": uuid.uuid4().hex[:8], "type": body.get("type", "cpu"),
               "duration_s": int(body.get("duration_s", 60)),
               "label": body.get("label", ""), "status": "starting", "elapsed_s": 0}
        _lt_active = lt
    asyncio.create_task(_run_lt(lt))
    return lt

@app.post("/api/loadtest/stop")
async def lt_stop():
    if _lt_active is None:
        return {"message": "No active test"}
    _lt_active["cancelled"] = True
    return {"message": "Cancellation requested", "id": _lt_active["id"]}

@app.post("/api/loadtest/schedule")
async def lt_schedule(body: dict):
    async with _lt_lock:
        s = {"id": uuid.uuid4().hex[:8], "type": body.get("type", "cpu"),
             "duration_s": int(body.get("duration_s", 60)),
             "start_iso": body.get("start_iso"), "repeat_s": body.get("repeat_s"),
             "repeat_end_iso": body.get("repeat_end_iso"), "label": body.get("label", "")}
        _lt_scheduled.append(s)
    return s

@app.delete("/api/loadtest/schedule/{sid}")
async def lt_cancel_scheduled(sid: str):
    global _lt_scheduled
    async with _lt_lock:
        before = len(_lt_scheduled)
        _lt_scheduled = [s for s in _lt_scheduled if s["id"] != sid]
    return {"removed": before - len(_lt_scheduled)}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
