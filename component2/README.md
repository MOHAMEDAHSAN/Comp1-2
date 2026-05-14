# Component 2 — Statistical Forecasting Engine

## Schema Contract
All canonical field names, types, and units are defined in **one place**:
→ [`../shared/SCHEMA.md`](../shared/SCHEMA.md)

Component 2's responsibilities with respect to the schema:
- **Consume** Part A (X features) from the `NormalizedObservation` stream
- **Produce** Part B (Y outputs) as `PlaybookFiringEvent` to Component 3
- **Never read** raw K8s metric names — only canonical fields from Part A

## Playbook → X Feature Mapping (quick reference)

| Playbook            | Key X Fields from shared/SCHEMA.md                                                    |
|---------------------|---------------------------------------------------------------------------------------|
| Probe-Cascade       | `pod.memory.working_set_pct`, `pod.probe.latency_ms`, `pod.probe.consecutive_failures`, `pod.restart_delta` |
| CPU-Contention      | `pod.cpu.throttle_ratio`, `node.cpu.usage_percent`, `node.cpu.pressure_waiting_rate`  |
| OOM-Cascade         | `pod.memory.working_set_pct`, `pod.memory.oom_events`, `node.memory.available_pct`    |
| gRPC-Degradation    | `node.net.tcp_retrans_rate`, `node.net.dns_latency_p99_ms`, `service.error_rate`      |
| Storage-Saturation  | `node.storage.disk_io_weighted_rate`, `pod.storage.used_pct`, `pvc.phase`             |

## Output Contract
All output fields are defined in `shared/SCHEMA.md` Part B.
Firing threshold: `confidence ≥ 0.65`

## Calibration Parameters

```yaml
global:
  baseline_window_hours: 24
  min_calibration_samples: 48       # No firing until 48 observations seen
  confidence_threshold: 0.65
  baseline_reset_events: [deploy, scale, config_change]

playbook_thresholds:
  probe-cascade:
    memory_z_threshold: 3.0
    probe_latency_z_threshold: 2.0

  cpu-contention:
    throttle_ratio_threshold: 0.30
    node_cpu_pct_threshold: 90.0
    psi_cpu_waiting_threshold: 0.20

  oom-cascade:
    memory_z_threshold: 3.0
    node_memory_available_pct_min: 10.0

  grpc-degradation:
    tcp_retrans_ratio_threshold: 0.01
    dns_latency_p99_ms_threshold: 100
    conntrack_utilization_threshold: 0.85

  storage-saturation:
    io_weighted_z_threshold: 2.0
    io_psi_waiting_threshold: 0.10
    pvc_used_pct_threshold: 85.0
```
