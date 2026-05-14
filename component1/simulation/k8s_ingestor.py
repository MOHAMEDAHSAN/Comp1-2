"""
k8s_ingestor.py — Real Kubernetes data ingestor
Reads live pod/node/service data from a running K8s cluster via the Python
kubernetes client (same kubeconfig kubectl uses).
Falls back gracefully if the cluster is unreachable.
"""
import time
from typing import Optional, Dict, Any

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    _K8S_LIB = True
except ImportError:
    _K8S_LIB = False


# ── helpers ───────────────────────────────────────────────────────────────────
def _parse_cpu(s: str) -> float:
    """CPU string → millicores  (e.g. '125m'→125, '1'→1000, '500000n'→0.5)"""
    if not s:
        return 0.0
    if s.endswith('n'):
        return float(s[:-1]) / 1_000_000
    if s.endswith('u'):
        return float(s[:-1]) / 1_000
    if s.endswith('m'):
        return float(s[:-1])
    return float(s) * 1000


def _parse_mem(s: str) -> int:
    """Memory string → bytes  (e.g. '256Mi'→268435456)"""
    if not s:
        return 0
    for suf, mult in [('Ti', 1 << 40), ('Gi', 1 << 30), ('Mi', 1 << 20),
                      ('Ki', 1 << 10), ('T', 10**12), ('G', 10**9),
                      ('M', 10**6), ('K', 10**3)]:
        if s.endswith(suf):
            return int(s[:-len(suf)]) * mult
    return int(s)


# ── ingestor class ────────────────────────────────────────────────────────────
class K8sIngestor:
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._ready = False
        if not _K8S_LIB:
            print("[k8s] 'kubernetes' package not installed — run: pip install kubernetes", flush=True)
            return
        try:
            config.load_kube_config()
            self.v1       = client.CoreV1Api()
            self.apps_v1  = client.AppsV1Api()
            self.custom   = client.CustomObjectsApi()
            # Quick connectivity test (short timeout)
            self.v1.list_node(_request_timeout=4)
            self._ready = True
            print("[k8s] Connected to Kubernetes cluster -- using REAL data", flush=True)
        except Exception as exc:
            print(f"[k8s] Cluster not reachable ({exc.__class__.__name__}) — using simulation", flush=True)

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── internal metric helpers ───────────────────────────────────────────────
    def _pod_metrics(self) -> Dict[str, Dict]:
        """pod-key → {cpu_mc, mem_bytes} from metrics-server"""
        out = {}
        try:
            if self.namespace:
                raw = self.custom.list_namespaced_custom_object(
                    "metrics.k8s.io", "v1beta1", self.namespace, "pods")
            else:
                raw = self.custom.list_cluster_custom_object(
                    "metrics.k8s.io", "v1beta1", "pods")
            for item in raw.get("items", []):
                key = f"{item['metadata']['namespace']}/{item['metadata']['name']}"
                containers = item.get("containers", [])
                out[key] = {
                    "cpu_mc":    sum(_parse_cpu(c["usage"].get("cpu", "0")) for c in containers),
                    "mem_bytes": sum(_parse_mem(c["usage"].get("memory", "0")) for c in containers),
                }
        except ApiException:
            pass   # metrics-server not installed — leave dict empty
        return out

    def _node_metrics(self) -> Dict[str, Dict]:
        """node-name → {cpu_mc, mem_bytes} from metrics-server"""
        out = {}
        try:
            raw = self.custom.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
            for item in raw.get("items", []):
                out[item["metadata"]["name"]] = {
                    "cpu_mc":    _parse_cpu(item["usage"].get("cpu", "0")),
                    "mem_bytes": _parse_mem(item["usage"].get("memory", "0")),
                }
        except ApiException:
            pass
        return out

    # ── main collect ──────────────────────────────────────────────────────────
    def collect(self) -> Optional[Dict[str, Any]]:
        if not self._ready:
            return None
        try:
            return self._build_observation()
        except Exception as exc:
            print(f"[k8s] collect error: {exc}", flush=True)
            return None

    def _build_observation(self) -> Dict[str, Any]:
        ns = self.namespace
        if ns:
            pods     = self.v1.list_namespaced_pod(namespace=ns).items
            services = self.v1.list_namespaced_service(namespace=ns).items
        else:
            pods     = self.v1.list_pod_for_all_namespaces().items
            services = self.v1.list_service_for_all_namespaces().items
        nodes    = self.v1.list_node().items
        pm       = self._pod_metrics()
        nm       = self._node_metrics()

        # ── Pod metrics ──────────────────────────────────────────────────────
        pod_metrics = []
        for pod in pods:
            p_ns   = pod.metadata.namespace
            p_name = pod.metadata.name
            key    = f"{p_ns}/{p_name}"

            # Resource limits from spec
            cpu_lim_mc, mem_lim_b = 0.0, 0
            for c in (pod.spec.containers or []):
                lim = (c.resources.limits or {}) if c.resources else {}
                cpu_lim_mc += _parse_cpu(lim.get("cpu", "0"))
                mem_lim_b  += _parse_mem(lim.get("memory", "0"))

            usage       = pm.get(key, {})
            cpu_use_mc  = usage.get("cpu_mc", 0.0)
            mem_use_b   = usage.get("mem_bytes", 0)
            cpu_pct     = round((cpu_use_mc / max(1, cpu_lim_mc)) * 100, 2) if cpu_lim_mc else 0.0
            mem_pct     = round((mem_use_b  / max(1, mem_lim_b )) * 100, 2) if mem_lim_b  else 0.0

            # Phase & restarts
            phase = pod.status.phase or "Unknown"
            restarts, last_reason = 0, "unknown"
            for cs in (pod.status.container_statuses or []):
                restarts += cs.restart_count or 0
                if cs.last_state and cs.last_state.terminated:
                    last_reason = cs.last_state.terminated.reason or "unknown"

            # Readiness probe
            ready = True
            for cond in (pod.status.conditions or []):
                if cond.type == "Ready":
                    ready = cond.status == "True"

            pod_metrics.append({
                "pod.id":                    key,
                "pod.namespace":             p_ns,
                "pod.node_name":             pod.spec.node_name or "",
                "pod.phase":                 phase,
                "pod.labels":                pod.metadata.labels or {},
                "pod.last_terminated_reason": last_reason,
                "pod.restart_count":         restarts,
                "pod.restart_delta":         0,
                "pod.crash_loop_active":     restarts > 5,
                "pod.cpu.usage_percent":     cpu_pct,
                "pod.cpu.throttle_ratio":    0.0,
                "pod.cpu.throttle_ms":       0.0,
                "pod.memory.working_set_bytes": mem_use_b,
                "pod.memory.working_set_pct":   mem_pct,
                "pod.memory.rss_bytes":      int(mem_use_b * 0.8),
                "pod.memory.limit_hit_count":0,
                "pod.memory.oom_events":     0,
                "pod.memory.major_fault_rate": 0.0,
                "pod.probe.type":            "readiness",
                "pod.probe.latency_ms":      0,
                "pod.probe.consecutive_failures": 0,
                "pod.probe.last_succeeded":  ready,
                "pod.probe.failure_event_count": 0,
                "pod.net.rx_bytes_rate":     0.0,
                "pod.net.tx_bytes_rate":     0.0,
                "pod.net.rx_drop_rate":      0.0,
                "pod.storage.used_bytes":    0,
                "pod.storage.capacity_bytes": 1 << 30,
                "pod.storage.used_pct":      0.0,
            })

        # ── Node metrics ─────────────────────────────────────────────────────
        node_metrics = []
        for node in nodes:
            n_name = node.metadata.name
            cap    = node.status.capacity    or {}
            usage  = nm.get(n_name, {})
            cpu_cap_mc  = _parse_cpu(cap.get("cpu",    "0"))
            mem_total_b = _parse_mem(cap.get("memory", "0"))
            cpu_use_mc  = usage.get("cpu_mc",    0.0)
            mem_use_b   = usage.get("mem_bytes", 0)
            mem_avail_b = max(0, mem_total_b - mem_use_b)
            cpu_pct     = round((cpu_use_mc / max(1, cpu_cap_mc)) * 100, 2)
            mem_avail_pct = round((mem_avail_b / max(1, mem_total_b)) * 100, 2)

            conds = [c.type for c in (node.status.conditions or []) if c.status == "True"]
            node_metrics.append({
                "node.name":                    n_name,
                "node.conditions":              conds,
                "node.schedulable":             not (node.spec.unschedulable or False),
                "node.cpu.usage_percent":       cpu_pct,
                "node.cpu.pressure_waiting_rate": 0.0,
                "node.cpu.sched_wait_ratio":    0.0,
                "node.cpu.load1":               0.0,
                "node.memory.available_bytes":  mem_avail_b,
                "node.memory.available_pct":    mem_avail_pct,
                "node.memory.pressure_waiting_rate": 0.0,
                "node.storage.disk_io_weighted_rate": 0.0,
                "node.storage.io_pressure_waiting_rate": 0.0,
                "node.storage.fs_available_bytes": 0,
                "node.storage.csi_attach_latency_ms": 0,
                "node.net.tcp_retrans_rate":    0.0,
                "node.net.tcp_syn_retrans_rate":0.0,
                "node.net.conntrack_utilization": 0.0,
                "node.net.dns_latency_p99_ms":  0,
                "node.net.dns_servfail_rate":   0.0,
            })

        # ── Service metrics ───────────────────────────────────────────────────
        service_metrics = []
        try:
            if ns:
                deps = self.apps_v1.list_namespaced_deployment(namespace=ns).items
            else:
                deps = self.apps_v1.list_deployment_for_all_namespaces().items
        except ApiException:
            deps = []

        dep_map = {d.metadata.name: d for d in deps}
        for svc in services:
            if svc.metadata.name == "kubernetes":
                continue
            svc_id = f"{svc.metadata.namespace}/{svc.metadata.name}"
            dep    = dep_map.get(svc.metadata.name)
            service_metrics.append({
                "service.id":                  svc_id,
                "service.ready_replicas":      (dep.status.ready_replicas or 0) if dep else 0,
                "service.unavailable_replicas":(dep.status.unavailable_replicas or 0) if dep else 0,
                "service.hpa_current_replicas":(dep.status.ready_replicas or 0) if dep else 0,
                "service.hpa_desired_replicas":(dep.spec.replicas or 0) if dep else 0,
                "service.latency_p50_ms":      0,
                "service.latency_p99_ms":      0,
                "service.error_rate":          0.0,
                "service.qps":                 0.0,
            })

        return {
            "tenant_id":    "k8s-live",
            "cluster_name": "local-cluster",
            "timestamp_ms": int(time.time() * 1000),
            "capability": {
                "capability.has_kubernetes_api":  True,
                "capability.has_prometheus":      False,
                "capability.has_kubelet_metrics": True,
                "capability.has_logs":            True,
                "capability.has_service_mesh":    False,
                "capability.degraded_playbooks":  {},
            },
            "pod_metrics":     pod_metrics,
            "node_metrics":    node_metrics,
            "service_metrics": service_metrics,
            "pvc_metrics":     [],
            "events":          [],
            "_sim_tick":       int(time.time()),
            "_scenario":       "real-k8s",
        }
