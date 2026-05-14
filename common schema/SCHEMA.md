# Unified Canonical Schema
## Single Source of Truth — Component 1 ↔ Component 2 Contract

> **Rule**: Every field name, type, and unit defined here is the law.
> Component 1 is responsible for *populating* these fields.
> Component 2 is responsible for *consuming* them as X features and *emitting* Y outputs.
> Neither component may invent its own field names.

---

## Data Flow

```
K8s Cluster
    │
    │  Raw metrics (Prometheus, Kubelet, K8s API, Events)
    ▼
┌─────────────┐    NormalizedObservation    ┌─────────────┐    PlaybookFiringEvent
│ Component 1 │ ─────────────────────────► │ Component 2 │ ──────────────────────► Component 3
│  (collects) │    [this schema = X]        │  (predicts) │    [this schema = Y]
└─────────────┘                             └─────────────┘
```

---

## Part A — Canonical Field Registry (X Features)

> These are the fields Component 1 writes and Component 2 reads.
> Column "C1 Source" = where C1 gets the raw value.
> Column "C2 Playbook" = which playbook(s) use this field.

### A1. Observation Envelope

| Canonical Field      | Type    | Unit          | C1 Source              | Required |
|----------------------|---------|---------------|------------------------|----------|
| `tenant_id`          | string  | —             | Agent config           | ✅ always |
| `cluster_name`       | string  | —             | Agent config           | ✅ always |
| `timestamp_ms`       | int64   | ms epoch UTC  | System clock           | ✅ always |

### A2. Capability Flags

| Canonical Field                    | Type   | C1 Source         | Notes                                  |
|------------------------------------|--------|-------------------|----------------------------------------|
| `capability.has_kubernetes_api`    | bool   | Self-test         | False → all playbooks disabled         |
| `capability.has_prometheus`        | bool   | Self-test         | False → metric playbooks partial       |
| `capability.has_kubelet_metrics`   | bool   | Self-test         | False → Probe-Cascade partial          |
| `capability.has_logs`              | bool   | Self-test         | False → OOM/Probe context missing      |
| `capability.has_service_mesh`      | bool   | Self-test         | False → gRPC-Degradation partial       |
| `capability.degraded_playbooks`    | map    | Derived           | `{playbook_id → "full|partial|off"}`   |

### A3. Pod-Level Features

| Canonical Field                    | Type    | Unit      | C1 Source (raw metric)                              | C2 Playbook          |
|------------------------------------|---------|-----------|-----------------------------------------------------|----------------------|
| `pod.id`                           | string  | —         | `namespace/pod-name`                                | all                  |
| `pod.namespace`                    | string  | —         | K8s API                                             | all                  |
| `pod.node_name`                    | string  | —         | K8s API                                             | all                  |
| `pod.phase`                        | string  | enum      | `kube_pod_status_phase`                             | all                  |
| `pod.labels`                       | map     | —         | K8s API `.metadata.labels`                          | baselining scope     |
| `pod.last_terminated_reason`       | string  | enum      | `kube_pod_container_status_last_terminated_reason`  | OOM, Probe-Cascade   |
| `pod.restart_count`                | int32   | count     | `kube_pod_container_status_restarts_total`          | Probe-Cascade        |
| `pod.restart_delta`                | int32   | count/30s | Δ restart_count over observation window             | Probe-Cascade        |
| `pod.crash_loop_active`            | bool    | —         | CrashLoopBackOff event present in window            | Probe-Cascade        |
| **CPU**                            |         |           |                                                     |                      |
| `pod.cpu.usage_percent`            | float64 | %         | rate(`container_cpu_usage_seconds_total`)           | CPU-Contention       |
| `pod.cpu.throttle_ratio`           | float64 | 0–1       | throttled_periods / total_periods                   | CPU-Contention       |
| `pod.cpu.throttle_ms`              | float64 | ms        | rate(`container_cpu_cfs_throttled_seconds_total`)   | CPU-Contention       |
| **Memory**                         |         |           |                                                     |                      |
| `pod.memory.working_set_bytes`     | int64   | bytes     | `container_memory_working_set_bytes`                | OOM, Probe-Cascade   |
| `pod.memory.working_set_pct`       | float64 | %         | working_set / limit × 100                          | OOM, Probe-Cascade   |
| `pod.memory.rss_bytes`             | int64   | bytes     | `container_memory_rss`                              | OOM-Cascade          |
| `pod.memory.limit_hit_count`       | int32   | count     | `container_memory_failcnt`                          | OOM-Cascade          |
| `pod.memory.oom_events`            | int32   | count     | `container_oom_events_total`                        | OOM-Cascade          |
| `pod.memory.major_fault_rate`      | float64 | faults/s  | rate(`container_memory_failures_total{pgmajfault}`) | OOM-Cascade          |
| **Probes**                         |         |           |                                                     |                      |
| `pod.probe.type`                   | string  | enum      | Kubelet probe config (`liveness/readiness/startup`) | Probe-Cascade        |
| `pod.probe.latency_ms`             | int32   | ms        | Kubelet probe execution time                        | Probe-Cascade        |
| `pod.probe.consecutive_failures`   | int32   | count     | Kubelet probe manager                               | Probe-Cascade        |
| `pod.probe.last_succeeded`         | bool    | —         | Kubelet probe manager                               | Probe-Cascade        |
| `pod.probe.failure_event_count`    | int32   | count     | K8s Events `Unhealthy`/`ProbeWarning` in window     | Probe-Cascade        |
| **Network**                        |         |           |                                                     |                      |
| `pod.net.rx_bytes_rate`            | float64 | bytes/s   | rate(`container_network_receive_bytes_total`)       | gRPC-Degradation     |
| `pod.net.tx_bytes_rate`            | float64 | bytes/s   | rate(`container_network_transmit_bytes_total`)      | gRPC-Degradation     |
| `pod.net.rx_drop_rate`             | float64 | pkts/s    | rate(`container_network_receive_packets_dropped_total`) | gRPC-Degradation |
| **Storage**                        |         |           |                                                     |                      |
| `pod.storage.used_bytes`           | int64   | bytes     | `kubelet_volume_stats_used_bytes`                   | Storage-Saturation   |
| `pod.storage.capacity_bytes`       | int64   | bytes     | `kubelet_volume_stats_capacity_bytes`               | Storage-Saturation   |
| `pod.storage.used_pct`             | float64 | %         | used / capacity × 100                              | Storage-Saturation   |

### A4. Node-Level Features

| Canonical Field                    | Type    | Unit      | C1 Source (raw metric)                              | C2 Playbook          |
|------------------------------------|---------|-----------|-----------------------------------------------------|----------------------|
| `node.name`                        | string  | —         | K8s API                                             | all                  |
| `node.conditions`                  | string[]| enum[]    | `kube_node_status_condition`                        | all                  |
| `node.schedulable`                 | bool    | —         | K8s API `.spec.unschedulable`                       | all                  |
| **CPU**                            |         |           |                                                     |                      |
| `node.cpu.usage_percent`           | float64 | %         | 1 - rate(`node_cpu_seconds_total{idle}`)            | CPU-Contention       |
| `node.cpu.pressure_waiting_rate`   | float64 | 0–1       | rate(`node_pressure_cpu_waiting_seconds_total`)     | CPU-Contention       |
| `node.cpu.sched_wait_ratio`        | float64 | 0–1       | waiting / (waiting + running) schedstat             | CPU-Contention       |
| `node.cpu.load1`                   | float64 | —         | `node_load1`                                        | CPU-Contention       |
| **Memory**                         |         |           |                                                     |                      |
| `node.memory.available_bytes`      | int64   | bytes     | `node_memory_MemAvailable_bytes`                    | OOM-Cascade          |
| `node.memory.available_pct`        | float64 | %         | available / total × 100                            | OOM-Cascade          |
| `node.memory.pressure_waiting_rate`| float64 | 0–1       | rate(`node_pressure_memory_waiting_seconds_total`)  | OOM-Cascade          |
| **Storage / IO**                   |         |           |                                                     |                      |
| `node.storage.disk_io_weighted_rate`| float64| 0–1       | rate(`node_disk_io_time_weighted_seconds_total`)    | Storage-Saturation   |
| `node.storage.io_pressure_waiting_rate`| float64 | 0–1   | rate(`node_pressure_io_waiting_seconds_total`)      | Storage-Saturation   |
| `node.storage.fs_available_bytes`  | int64   | bytes     | `node_filesystem_avail_bytes{mountpoint="/"}`       | Storage-Saturation   |
| `node.storage.csi_attach_latency_ms`| int32  | ms        | `csi_operations_seconds{ControllerPublishVolume}` p99 | Storage-Saturation |
| **Network**                        |         |           |                                                     |                      |
| `node.net.tcp_retrans_rate`        | float64 | ratio     | retrans / out_segs                                  | gRPC-Degradation     |
| `node.net.tcp_syn_retrans_rate`    | float64 | count/s   | rate(`node_netstat_TcpExt_TCPSynRetrans`)           | gRPC-Degradation     |
| `node.net.conntrack_utilization`   | float64 | 0–1       | entries / entries_limit                             | gRPC-Degradation     |
| `node.net.dns_latency_p99_ms`      | int32   | ms        | `coredns_dns_request_duration_seconds` p99          | gRPC-Degradation     |
| `node.net.dns_servfail_rate`       | float64 | count/s   | rate(`coredns_dns_response_rcode_count_total{SERVFAIL}`) | gRPC-Degradation |

### A5. Service-Level Features

| Canonical Field                    | Type    | Unit      | C1 Source (raw metric)                              | C2 Playbook          |
|------------------------------------|---------|-----------|-----------------------------------------------------|----------------------|
| `service.id`                       | string  | —         | `namespace/service-name`                            | all                  |
| `service.ready_replicas`           | int32   | count     | `kube_deployment_status_replicas_available`         | all                  |
| `service.unavailable_replicas`     | int32   | count     | `kube_deployment_status_replicas_unavailable`       | Probe-Cascade        |
| `service.hpa_current_replicas`     | int32   | count     | `kube_horizontalpodautoscaler_status_current_replicas` | CPU-Contention    |
| `service.hpa_desired_replicas`     | int32   | count     | `kube_horizontalpodautoscaler_status_desired_replicas` | CPU-Contention    |
| `service.latency_p50_ms`           | int32   | ms        | Prometheus/mesh `request_duration_seconds` p50      | gRPC-Degradation     |
| `service.latency_p99_ms`           | int32   | ms        | Prometheus/mesh `request_duration_seconds` p99      | gRPC-Degradation     |
| `service.error_rate`               | float64 | 0–1       | 5xx / total requests                                | gRPC-Degradation     |
| `service.qps`                      | float64 | req/s     | rate(requests_total)                                | gRPC-Degradation     |

### A6. PVC Features

| Canonical Field                    | Type    | Unit      | C1 Source (raw metric)                              | C2 Playbook          |
|------------------------------------|---------|-----------|-----------------------------------------------------|----------------------|
| `pvc.id`                           | string  | —         | `namespace/pvc-name`                                | Storage-Saturation   |
| `pvc.phase`                        | string  | enum      | `kube_persistentvolumeclaim_status_phase`           | Storage-Saturation   |
| `pvc.pending_duration_ms`          | int64   | ms        | Derived: age when phase=Pending                     | Storage-Saturation   |

### A7. Cluster Events

| Canonical Field         | Type   | Values                                         | C1 Source                       | C2 Playbook        |
|-------------------------|--------|------------------------------------------------|---------------------------------|--------------------|
| `event.type`            | string | `pod_restart`, `deploy`, `scale`,              | K8s Events API                  | all (context)      |
|                         |        | `oom_kill`, `eviction`, `probe_failure`,        |                                 |                    |
|                         |        | `node_condition`, `storage_error`              |                                 |                    |
| `event.affected_id`     | string | resource path                                  | K8s Events `.involvedObject`    | all                |
| `event.severity`        | string | `info`, `warning`, `error`                     | K8s Events `.type`              | all                |
| `event.timestamp_ms`    | int64  | ms epoch                                       | K8s Events `.lastTimestamp`     | all                |
| `event.count`           | int32  | occurrences in window                          | K8s Events `.count`             | all                |
| `event.reason`          | string | raw K8s reason string                          | K8s Events `.reason`            | debugging context  |

---

## Part B — Output Schema (Y Features)

> These are fields Component 2 writes. Component 3 reads them.
> Component 1 never writes these.

### B1. Intermediate Per-Metric Outputs (computed inside C2 per observation)

| Field                         | Type    | Unit  | Description                                   |
|-------------------------------|---------|-------|-----------------------------------------------|
| `baseline.mean`               | float64 | same  | Pooled-σ mean over 24h sliding windows        |
| `baseline.stddev`             | float64 | same  | Pooled standard deviation                     |
| `baseline.z_score`            | float64 | σ     | (current − mean) / stddev                     |
| `baseline.anomaly_flag`       | bool    | —     | True if \|z_score\| > threshold               |
| `baseline.trend`              | string  | enum  | `rising`, `stable`, `falling`                 |
| `baseline.sample_count`       | int32   | —     | Samples used; < 48 = not yet calibrated       |
| `baseline.reset_reason`       | string  | —     | Last reset cause (`deploy`, `scale`, `init`)  |

### B2. PlaybookFiringEvent (emitted to Component 3)

| Field                         | Type     | Description                                            |
|-------------------------------|----------|--------------------------------------------------------|
| `playbook_id`                 | string   | `probe-cascade` / `cpu-contention` / `oom-cascade` / `grpc-degradation` / `storage-saturation` |
| `tenant_id`                   | string   | Same as observation envelope                           |
| `cluster_name`                | string   | Same as observation envelope                           |
| `timestamp_ms`                | int64    | When event fired                                       |
| `firing_state`                | string   | `FIRING` → `RESOLVING` → `RESOLVED`                   |
| `confidence`                  | float64  | 0.0–1.0                                                |
| `affected_pod_ids`            | string[] | `namespace/pod-name` list                              |
| `affected_node_names`         | string[] | Node name list                                         |
| `affected_service_ids`        | string[] | `namespace/service-name` list                          |
| `evidence.variable_values`    | map      | Snapshot of canonical X values at fire time            |
| `evidence.z_scores`           | map      | Z-scores of the same X fields at fire time             |
| `evidence.conditions_met`     | string[] | Ordered list of conditions that triggered the playbook |
| `evidence.conditions_missed`  | string[] | Conditions checked but not met (explains < 1.0 confidence) |
| `reason`                      | string   | Human-readable explanation for Component 3 / operator |

### B3. Confidence Scoring Rules (uniform across all playbooks)

```
evidence_count = number of conditions met out of total required
required_count = number of conditions defined in playbook

confidence = evidence_count / required_count × weight_adjustment

where weight_adjustment accounts for:
  - Sequential ordering bonus  (+0.1 if conditions fired in expected order)
  - Log pattern match bonus    (+0.05 if matching log signature found)
  - Recency bonus              (+0.05 if all conditions within last 90s)

Firing threshold: confidence ≥ 0.65
```

---

## Part C — Data Types & Units (enforced by both components)

| Category   | Type    | Unit Convention           | Enforcement Rule                      |
|------------|---------|---------------------------|---------------------------------------|
| CPU        | float64 | `%` (0–100)               | Never use raw core-seconds directly   |
| Memory     | int64   | bytes                     | Never use KB/MB/GB                    |
| Ratios     | float64 | 0.0–1.0                   | Not percent — raw ratio               |
| Latency    | int32   | milliseconds              | All latency fields end in `_ms`       |
| Rates      | float64 | per-second                | All rate fields end in `_rate`        |
| Counts     | int32   | non-negative              | Never negative                        |
| Timestamps | int64   | ms since UTC epoch        | All timestamp fields end in `_ms`     |
| Enums      | string  | defined values only       | Unknown maps to `"unknown"`, not null |
| Booleans   | bool    | true/false                | No string "true"/"false"              |

---

## Part C — Capability-to-Playbook Degradation Map

```
Missing Capability          → Affected Playbooks         → Mode
──────────────────────────────────────────────────────────────────────────────
has_kubernetes_api = false  → ALL                        → DISABLED
has_prometheus = false      → cpu-contention             → PARTIAL (no throttle)
                            → oom-cascade                → PARTIAL (no PSI)
                            → storage-saturation         → PARTIAL (no IO weighted)
has_kubelet_metrics = false → probe-cascade              → PARTIAL (no probe data)
has_logs = false            → oom-cascade, probe-cascade → PARTIAL (no crash context)
has_service_mesh = false    → grpc-degradation           → PARTIAL (no latency/QPS)
eBPF (not in v1)            → none                       → No impact
```

---

## Revision Policy

> Any change to a canonical field name, type, or unit **must** be agreed by both
> the Component 1 and Component 2 teams before merging. Update this file,
> then update `observability.proto` to match. The proto is generated from this schema,
> not the other way around.

---

## Appendix — Why We Chose These Features & Labels

> This section explains the **reasoning** behind every selection decision.
> It is not required reading to implement the schema, but it is required reading
> to understand why the schema looks the way it does.

---

### Why These X Features (Inputs)?

The inventory (`k8s_data_inventory.xlsx`) catalogues 760+ observable data points
across 13 sheets. We did not pick randomly — every feature here was selected by
applying three filters:

#### Filter 1 — Causal relevance to a known failure mode
Every metric must sit on a **proven causal chain** leading to one of the 5 failure
modes the system is designed to detect. We used the pre-experimentation spike data
(`Pre-experimentation/k8s-spike/trials_*/`) as ground truth: if a metric moved
before or during a real induced failure, it earned its place.

Example:
```
container_cpu_cfs_throttled_periods_total  ← showed sustained rise in trial_1
  before probe timeouts appeared           ← pod.probe.latency_ms rose 2 trials later
  before restart events appeared           ← pod.restart_delta went non-zero last
```
This ordering confirmed the causal chain for **Probe-Cascade** and **CPU-Contention**.

#### Filter 2 — Native or Tier 1 only (v1 scope)
The Excel inventory explicitly tiers every data point:
- **Native**: available on *any* conformant K8s cluster, no extra tools
- **Tier 1**: requires standard production tooling (node-exporter, kube-state-metrics,
  Prometheus, Fluent Bit) — broadly deployed and expected in real customer environments
- **Tier 2**: eBPF-based or niche (Pixie, Parca, Tetragon) — not assumed present

We excluded all Tier 2 metrics from v1. This keeps the agent deployable on vanilla
clusters without asking customers to install exotic tooling.

#### Filter 3 — Non-redundant information content
Where multiple metrics measure the same underlying phenomenon, we kept the
**most actionable one** and dropped duplicates:

| Dropped (redundant)                     | Kept (more actionable)             | Reason                                           |
|-----------------------------------------|------------------------------------|--------------------------------------------------|
| `container_memory_usage_bytes`          | `container_memory_working_set_bytes` | WSS is what OOM killer compares — usage includes reclaimable cache |
| `node_memory_MemFree_bytes`             | `node_memory_MemAvailable_bytes`   | Available accounts for reclaimable cache; Free does not |
| `node_disk_reads_completed_total`       | `node_disk_io_time_weighted_seconds_total` | Weighted time captures latency × queue depth; raw IOPS alone misses backlog |
| `container_network_transmit_errors_total` | `container_network_receive_packets_dropped_total` | Drops are a stronger saturation signal than errors |
| Raw `node_cpu_seconds_total`            | Derived `node.cpu.usage_percent`   | Derived form is directly comparable; raw requires rate() math in C2 |

---

### Why These Y Labels (Outputs)?

The 5 playbook labels are not arbitrary — they map exactly to the **5 most common
Kubernetes failure patterns** documented in incident post-mortems and confirmed by
the pre-experimentation spike data.

#### Label 1: `probe_cascade_score` (Probe-Cascade)

**Why this label?**
Probe failures are the most common cause of unexpected pod restarts in production
Kubernetes clusters. The causal chain is:
```
Memory pressure  →  app response slows  →  liveness probe times out
  →  kubelet kills container  →  restart loop  →  CrashLoopBackOff
```
This is detectable *early* (at the memory pressure stage) before the restart loop
becomes visible. Early detection gives operators time to act (raise memory limit,
reduce probe frequency) before availability is impacted.

**Why not just alert on restarts directly?**
By the time restarts are visible, the failure has already happened. The probe-cascade
label fires at the *precursor* stage — memory + probe latency rising together —
giving a 30–90 second lead time based on spike trial observations.

---

#### Label 2: `cpu_contention_score` (CPU Contention)

**Why this label?**
On single-node or resource-constrained clusters, multiple workloads compete for CPU.
CFS throttling is invisible to the application — the container doesn't "know" it's
being throttled — but the effect accumulates as request latency and eventually as
probe timeouts. The causal chain:
```
Shared-core contention  →  CFS throttle ratio rises  →  app request latency rises
  →  liveness probe timeout  →  restart
```
**Why `throttle_ratio` specifically?**
Raw CPU usage (`usage_percent`) can look normal while throttling is severe. A container
can be at 70% CPU usage but 80% of its scheduling slots are being throttled — the
distinction only shows up in `cfs_throttled_periods / total_periods`. This is
documented in the inventory (AI Agent Mapping sheet, CPU Analysis Agent row 7) and
confirmed in `trial_1` and `trial_2` of `trials_linux/`.

---

#### Label 3: `oom_cascade_score` (OOM Cascade)

**Why this label?**
OOM events are node-level phenomena that propagate. When one pod is OOMKilled, the
kernel reclaims memory — but if node-level memory pressure is already high, the
eviction manager starts evicting other pods too. This cascade is the difference between
a single pod failure and a namespace-wide outage.

**Why both pod-level and node-level features?**
- Pod-level (`working_set_pct`, `oom_events`) catches the *first victim*
- Node-level (`memory.available_pct`, `memory.pressure_waiting_rate`) catches
  whether conditions exist for *cascade* — a pod OOM on a healthy node is a minor
  event; the same OOM on a node at 92% memory is the start of a cascade

**Why `working_set_bytes` and not `usage_bytes`?**
`working_set_bytes` is exactly what the OOM killer compares against the memory limit.
`usage_bytes` includes page cache which is reclaimable — it would produce false signals.
This is stated explicitly in the inventory (AI Agent Mapping, Memory Analysis Agent row 1).

---

#### Label 4: `grpc_degradation_score` (gRPC Degradation)

**Why this label?**
gRPC relies on persistent HTTP/2 connections with strict timeout semantics. Network
impairment (packet loss, TCP retransmits, DNS slowness) that would be tolerable for
HTTP/1.1 (which retries at the application layer) can be catastrophic for gRPC — a
single retransmit during a streaming RPC causes the entire stream to stall until
the timeout fires. The causal chain:
```
TCP retransmits / DNS latency  →  gRPC deadline exceeded  →  service errors rise
  →  upstream services retry  →  fan-out amplifies load  →  cascade
```
**Why DNS latency specifically?**
In Kubernetes, every pod resolves service names via CoreDNS on every new connection.
Slow DNS is a silent killer — the app appears healthy, latency is just slightly
elevated, until a burst of new connections triggers mass DNS timeouts. The inventory
(AI Agent Mapping, Network Analysis Agent) flags `coredns_dns_request_duration_seconds`
p99 > 100ms as an active issue threshold.

**Why conntrack utilization?**
At high conntrack utilization (> 85% of `nf_conntrack_entries_limit`), the kernel
silently drops new flows. This is one of the most common "mystery outages" in
Kubernetes — the inventory explicitly calls this out as CRITICAL.

---

#### Label 5: `storage_saturation_score` (Storage Queue Saturation)

**Why this label?**
Storage I/O bottlenecks in Kubernetes manifest differently from application-level
slowness — they affect the entire node, not just one pod. A single pod doing heavy
writes can saturate the underlying block device and cause all other pods on the node
to experience slow filesystem operations, even if they are doing light I/O. The
causal chain:
```
High I/O workload  →  disk queue fills  →  io_time_weighted rises
  →  node PSI io_waiting rises  →  other pods hang on write()
  →  liveness probes time out  →  evictions / restarts
```
**Why `io_time_weighted` and not just IOPS?**
IOPS can be high and latency still acceptable if the device is fast. Conversely,
IOPS can be modest but latency catastrophic if there's a queue backlog.
`node_disk_io_time_weighted_seconds_total` captures **latency × queue depth** —
it rises when there is a backlog regardless of IOPS. The inventory (AI Agent Mapping,
Storage/PVC Analysis Agent) calls this the "KEY latency proxy".

**Why PVC pending duration?**
A PVC stuck in Pending for > 5 minutes means pods depending on it cannot start.
This is a silent failure — the pod shows `Pending` phase with no obvious error
unless you explicitly check the PVC. Including `pvc.pending_duration_ms` lets
the playbook catch provisioning failures before they cascade into restart loops.

---

### Why 5 Labels and Not More?

The 5 playbooks cover the failure modes that appeared in the pre-experimentation
spike data and match the most common Kubernetes incident categories in public
post-mortem literature. They were chosen to be:

1. **Mutually distinguishable** — each has a different primary evidence chain, so
   Component 2 can tell them apart even when they co-occur
2. **Actionable** — each maps to a specific operator action (raise memory limit,
   tune probes, scale out, fix DNS, add storage IOPS)
3. **Detectable with v1 data** — all evidence chains are observable at Native/Tier 1
4. **Extensible** — new playbooks can be added without changing the schema; they
   just reference existing canonical X fields

Tier 2 failure modes (e.g., CPU frequency throttling from thermal, NUMA topology
misalignment, eBPF-detected syscall anomalies) are explicitly deferred to v1.1.
They require Tier 2 data sources not assumed present in v1 deployments.
