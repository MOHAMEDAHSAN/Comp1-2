"""
load_gen.py  --  Kubernetes Spike Load Generator
Creates real CPU/memory pressure on Docker Desktop so the dashboard
shows non-zero metrics and the ingestor logs real schema data.

Usage:
  python load_gen.py cpu     deploy a CPU-stress pod  (2 CPUs, 5 min)
  python load_gen.py mem     deploy a memory-stress pod  (256 MB, 5 min)
  python load_gen.py crash   deploy a crash-loop pod  (restarts every 3 s)
  python load_gen.py http    hammer my-app via HTTP for 30 s
  python load_gen.py spike   all of the above simultaneously
  python load_gen.py clean   delete all load-gen pods
  python load_gen.py status  show pod states
"""
import subprocess, sys, time, threading, tempfile, os

# ── kubectl helper ────────────────────────────────────────────────────────────
def kube(args, capture=False):
    cmd = ["kubectl"] + args
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r.stdout.strip()
    subprocess.run(cmd, check=False)
    return ""

# ── Pod YAML definitions ──────────────────────────────────────────────────────
CPU_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: loadgen-cpu
  namespace: default
  labels: {app: loadgen, type: cpu-stress}
spec:
  containers:
  - name: stress
    image: polinux/stress
    args: ["stress","--cpu","2","--timeout","300s"]
    resources:
      requests: {cpu: "500m", memory: "64Mi"}
      limits:   {cpu: "1000m", memory: "128Mi"}
  restartPolicy: Never
"""

MEM_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: loadgen-mem
  namespace: default
  labels: {app: loadgen, type: mem-stress}
spec:
  containers:
  - name: stress
    image: polinux/stress
    args: ["stress","--vm","1","--vm-bytes","256M","--vm-hang","0","--timeout","300s"]
    resources:
      requests: {cpu: "100m", memory: "128Mi"}
      limits:   {cpu: "200m", memory: "512Mi"}
  restartPolicy: Never
"""

CRASH_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: loadgen-crash
  namespace: default
  labels: {app: loadgen, type: crash-loop}
spec:
  containers:
  - name: crasher
    image: busybox
    command: ["sh","-c","echo CRASHING; sleep 3; exit 1"]
    resources:
      requests: {cpu: "10m",  memory: "16Mi"}
      limits:   {cpu: "50m",  memory: "32Mi"}
  restartPolicy: Always
"""

PODS = {
    "cpu":   ("loadgen-cpu",   CPU_YAML),
    "mem":   ("loadgen-mem",   MEM_YAML),
    "crash": ("loadgen-crash", CRASH_YAML),
}

# ── helpers ───────────────────────────────────────────────────────────────────
def apply_yaml(yaml_str):
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    tmp.write(yaml_str); tmp.close()
    kube(["apply", "-f", tmp.name])
    os.unlink(tmp.name)

def delete_pod(name):
    print(f"  [k8s] Deleting {name}...")
    kube(["delete", "pod", name, "-n", "default", "--ignore-not-found"])

def wait_running(pod_name, timeout=60):
    print(f"  [k8s] Waiting for {pod_name} to start", end="", flush=True)
    for _ in range(timeout):
        phase = kube(["get", "pod", pod_name, "-n", "default",
                      "-o", "jsonpath={.status.phase}"], capture=True)
        if phase in ("Running", "Succeeded"):
            print(" OK"); return True
        print(".", end="", flush=True); time.sleep(1)
    print(" TIMEOUT"); return False

# ── HTTP load ─────────────────────────────────────────────────────────────────
def http_load(url, duration_s=30, concurrency=20):
    import urllib.request
    stop   = threading.Event()
    counts = {"ok": 0, "err": 0}
    lock   = threading.Lock()

    def worker():
        while not stop.is_set():
            try:
                urllib.request.urlopen(url, timeout=2)
                with lock: counts["ok"] += 1
            except Exception:
                with lock: counts["err"] += 1

    print(f"  [http] {concurrency} threads -> {url}  ({duration_s}s)")
    ts = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for t in ts: t.start()
    for i in range(duration_s):
        time.sleep(1)
        if i % 5 == 4:
            with lock:
                print(f"  [http] t={i+1:3d}s  OK={counts['ok']}  ERR={counts['err']}")
    stop.set()
    for t in ts: t.join(timeout=2)
    print(f"  [http] DONE  OK={counts['ok']}  ERR={counts['err']}")

# ── commands ──────────────────────────────────────────────────────────────────
def cmd_cpu():
    print("\n[LOAD] CPU stress pod (2 vCPU x 300s)...")
    name, yaml = PODS["cpu"]
    delete_pod(name); time.sleep(1)
    apply_yaml(yaml); wait_running(name)
    print("  -> Dashboard: Node CPU % should spike")

def cmd_mem():
    print("\n[LOAD] Memory stress pod (256 MB x 300s)...")
    name, yaml = PODS["mem"]
    delete_pod(name); time.sleep(1)
    apply_yaml(yaml); wait_running(name)
    print("  -> Dashboard: Node Memory available % should drop")

def cmd_crash():
    print("\n[LOAD] Crash-loop pod (exits every 3s, loops forever)...")
    name, yaml = PODS["crash"]
    delete_pod(name); time.sleep(1)
    apply_yaml(yaml)
    print("  -> Dashboard: restart_count increments; probe-fail badge appears")
    print("  -> Run: python load_gen.py clean  to stop it")

def cmd_http():
    port = kube(["get", "svc", "my-app", "-n", "default",
                 "-o", "jsonpath={.spec.ports[0].nodePort}"], capture=True)
    port = port if port.isdigit() else "30080"
    print(f"\n[LOAD] HTTP load -> http://localhost:{port}")
    http_load(f"http://localhost:{port}", duration_s=30, concurrency=20)

def cmd_spike():
    print("\n[SPIKE] Deploying all loads simultaneously...")
    ts = [threading.Thread(target=f) for f in (cmd_cpu, cmd_mem, cmd_crash)]
    for t in ts: t.start()
    for t in ts: t.join()
    cmd_http()
    print("\n[DONE] Spike complete. Data written every 5s poll cycle.")
    print("       Run: python load_gen.py clean  when finished.")

def cmd_clean():
    print("\n[CLEAN] Removing load-gen pods...")
    for name, _ in PODS.values():
        delete_pod(name)

def cmd_status():
    print("\n[STATUS] Current pod states:")
    kube(["get", "pods", "-n", "default", "--show-labels"])

# ── main ──────────────────────────────────────────────────────────────────────
CMDS = {
    "cpu": cmd_cpu, "mem": cmd_mem, "crash": cmd_crash,
    "http": cmd_http, "spike": cmd_spike,
    "clean": cmd_clean, "status": cmd_status,
}

if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""
    if arg not in CMDS:
        print(__doc__)
    else:
        CMDS[arg]()
