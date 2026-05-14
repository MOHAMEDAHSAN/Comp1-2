"""
validate_schema.py -- Checks saved .ndjson files match the Component-1 schema.

Usage:
  python validate_schema.py              scan all files in data/
  python validate_schema.py live         validate the live /api/state endpoint
  python validate_schema.py data/x.ndjson  validate a specific file
"""
import json, sys, os
from pathlib import Path

# ── Expected schema ───────────────────────────────────────────────────────────
TOP_KEYS = {
    "tenant_id": str, "cluster_name": str, "timestamp_ms": int,
    "capability": dict, "pod_metrics": list, "node_metrics": list,
    "service_metrics": list,
}

POD_KEYS = {
    "pod.id": str, "pod.namespace": str, "pod.node_name": str,
    "pod.phase": str, "pod.restart_count": int,
    "pod.crash_loop_active": bool,
    "pod.cpu.usage_percent": (int, float),
    "pod.cpu.throttle_ratio": (int, float),
    "pod.memory.working_set_bytes": int,
    "pod.memory.working_set_pct": (int, float),
    "pod.probe.last_succeeded": bool,
    "pod.probe.consecutive_failures": int,
    "pod.net.rx_bytes_rate": (int, float),
    "pod.net.tx_bytes_rate": (int, float),
    "pod.storage.used_pct": (int, float),
}

NODE_KEYS = {
    "node.name": str, "node.conditions": list, "node.schedulable": bool,
    "node.cpu.usage_percent": (int, float),
    "node.memory.available_pct": (int, float),
    "node.memory.available_bytes": int,
    "node.net.tcp_retrans_rate": (int, float),
    "node.net.dns_latency_p99_ms": (int, float),
    "node.storage.disk_io_weighted_rate": (int, float),
}

SVC_KEYS = {
    "service.id": str,
    "service.ready_replicas": int,
    "service.hpa_desired_replicas": int,
    "service.latency_p50_ms": (int, float),
    "service.error_rate": (int, float),
    "service.qps": (int, float),
}

CAP_KEYS = {
    "capability.has_kubernetes_api": bool,
    "capability.has_prometheus": bool,
    "capability.has_kubelet_metrics": bool,
    "capability.has_logs": bool,
    "capability.has_service_mesh": bool,
}

# ── Report ────────────────────────────────────────────────────────────────────
class Report:
    def __init__(self):
        self.errors   = []
        self.warnings = []
        self.ok       = 0

    def err(self, msg):  self.errors.append(msg)
    def warn(self, msg): self.warnings.append(msg)
    def good(self):      self.ok += 1


def check_fields(obj, schema, prefix, r):
    for key, expected_type in schema.items():
        if key not in obj:
            r.err(f"  MISSING  {prefix}.{key}")
        else:
            val = obj[key]
            if not isinstance(val, expected_type):
                r.err(f"  TYPE ERR {prefix}.{key} = {val!r} (expected {expected_type})")
            else:
                r.good()


def validate_obs(obs, obs_idx=0):
    r = Report()
    label = f"obs[{obs_idx}]"

    # Top-level keys
    for key, typ in TOP_KEYS.items():
        if key not in obs:
            r.err(f"  MISSING  {label}.{key}")
        elif not isinstance(obs[key], typ):
            r.err(f"  TYPE ERR {label}.{key} = {obs[key]!r} (expected {typ.__name__})")
        else:
            r.good()

    # Capability block
    cap = obs.get("capability", {})
    check_fields(cap, CAP_KEYS, f"{label}.capability", r)

    # Pod metrics
    pods = obs.get("pod_metrics", [])
    if not pods:
        r.warn(f"  {label}: pod_metrics is empty")
    for i, pod in enumerate(pods[:5]):
        check_fields(pod, POD_KEYS, f"{label}.pod[{i}]", r)
        cpu = pod.get("pod.cpu.usage_percent", -1)
        if not (0 <= cpu <= 200):
            r.warn(f"  {label}.pod[{i}] cpu={cpu} outside [0,200]")
        mem = pod.get("pod.memory.working_set_pct", -1)
        if not (0 <= mem <= 110):
            r.warn(f"  {label}.pod[{i}] mem_pct={mem} outside [0,110]")

    # Node metrics
    nodes = obs.get("node_metrics", [])
    if not nodes:
        r.warn(f"  {label}: node_metrics is empty")
    for i, node in enumerate(nodes):
        check_fields(node, NODE_KEYS, f"{label}.node[{i}]", r)

    # Service metrics
    for i, svc in enumerate(obs.get("service_metrics", [])):
        check_fields(svc, SVC_KEYS, f"{label}.service[{i}]", r)

    return r


def _print_report(r):
    print(f"\n  PASSED   : {r.ok} checks")
    print(f"  WARNINGS : {len(r.warnings)}")
    for w in r.warnings: print(f"   {w}")
    print(f"  ERRORS   : {len(r.errors)}")
    for e in r.errors:   print(f"   {e}")
    if not r.errors:
        print("\n  [PASS] Schema validation PASSED - all required fields present with correct types!")
    else:
        print("\n  [FAIL] Schema validation FAILED - see errors above.")


def validate_file(path):
    path = Path(path)
    if not path.exists():
        print(f"[ERROR] File not found: {path}")
        return
    print(f"\n{'='*60}")
    print(f"[FILE] {path.name}  ({path.stat().st_size // 1024} KB)")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    print(f"       {len(lines)} observations")

    total_r = Report()
    for i, line in enumerate(lines):
        try:
            obs = json.loads(line)
        except json.JSONDecodeError as e:
            total_r.err(f"  JSON PARSE ERROR line {i}: {e}")
            continue
        r = validate_obs(obs, i)
        total_r.errors   += r.errors
        total_r.warnings += r.warnings
        total_r.ok       += r.ok

    _print_report(total_r)


def validate_live():
    import urllib.request
    url = "http://localhost:8000/api/state"
    print(f"\n{'='*60}")
    print(f"[LIVE] Validating -> {url}")
    try:
        data = urllib.request.urlopen(url, timeout=5).read()
        obs  = json.loads(data)
    except Exception as e:
        print(f"[ERROR] Could not reach server: {e}")
        return

    if "_status" in obs and "pod_metrics" not in obs:
        print(f"[WARN] Server returned status only (no data yet): {obs}")
        return

    r = validate_obs(obs, 0)
    _print_report(r)

    # Print sample values
    pods  = obs.get("pod_metrics", [])
    nodes = obs.get("node_metrics", [])
    print(f"\n  Sample pod metrics ({len(pods)} pods):")
    for p in pods[:8]:
        cpu = p.get("pod.cpu.usage_percent", 0)
        mem = p.get("pod.memory.working_set_pct", 0)
        rst = p.get("pod.restart_count", 0)
        pid = p.get("pod.id", "?")
        print(f"    {pid:50s}  cpu={cpu:6.2f}%  mem={mem:6.2f}%  restarts={rst}")
    if nodes:
        n = nodes[0]
        print(f"\n  Node '{n['node.name']}':")
        print(f"    cpu={n.get('node.cpu.usage_percent',0):.2f}%  "
              f"mem_avail={n.get('node.memory.available_pct',0):.2f}%  "
              f"tcp_retrans={n.get('node.net.tcp_retrans_rate',0):.4f}")

    # Capability flags
    cap = obs.get("capability", {})
    print("\n  Capability flags:")
    for k, v in cap.items():
        if k.startswith("capability.has_"):
            status = "active " if v else "MISSING"
            print(f"    {k:45s} {status}")


# ── main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""

    if arg == "live":
        validate_live()
    elif arg and os.path.exists(arg):
        validate_file(arg)
    else:
        data_dir = Path(__file__).parent / "data"
        files    = sorted(data_dir.glob("*.ndjson")) if data_dir.exists() else []
        if not files:
            print("No .ndjson files in data/ yet.")
            print("  -> Run server for ~100s to auto-save, or POST to /api/save-now")
            print("  -> Use: python validate_schema.py live   to validate live endpoint")
        else:
            for f in files:
                validate_file(str(f))
