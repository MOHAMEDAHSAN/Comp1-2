# Component 1 — Data Ingestion & Normalization Plane

## Schema Contract
All canonical field names, types, and units are defined in **one place**:
→ [`../shared/SCHEMA.md`](../shared/SCHEMA.md)

Component 1's sole responsibility with respect to the schema:
- **Populate** every field in Part A (X features) from raw K8s sources
- **Never invent** field names not listed in `shared/SCHEMA.md`
- **Report** `capability_flags` accurately so Component 2 knows which fields are present

## Collection Priority Order
See `shared/SCHEMA.md` Part A — fields are grouped by playbook dependency.
Implement in this order:

| Priority | Section | Enables Playbook |
|----------|---------|-----------------|
| P1 | A1 Envelope + A2 Capability | All (baseline observation) |
| P2 | A3 Pod CPU + Memory + Restart | OOM-Cascade, Probe-Cascade |
| P3 | A3 Probes + A4 Node CPU/Mem | Probe-Cascade, CPU-Contention |
| P4 | A4 Node Storage/IO + A6 PVC | Storage-Saturation |
| P5 | A4 Node Network + A5 Service | gRPC-Degradation |
| P6 | A7 Events | All (context + reset triggers) |

## Simulation & Testing

A complete **synthetic Kubernetes cluster simulator** is available under [`./simulation/`](./simulation):

### What It Does
- Generates synthetic pod/node/service observations following the canonical schema
- Simulates realistic metrics with jitter and aggregation
- Supports deterministic fault injection patterns (OOM, CPU contention, probe cascade, etc.)
- Outputs observations in NDJSON format for Component 2 ingestion

### Quick Start
```bash
cd simulation
pip install -r requirements.txt
python test_run.py
```

This generates `observations_baseline.ndjson` (100 observations) that can be fed directly to Component 2.

### Scenarios Supported
- **baseline** — Healthy cluster (calibration)
- **oom_cascade** — Memory leak → OOM → node evictions
- **cpu_contention** — CPU throttling → probe timeout → restarts
- **probe_cascade** — Memory pressure → probe latency → failures
- **grpc_degradation** — Network packet loss → service degradation
- **storage_saturation** — PVC space exhaustion

See [`./simulation/README.md`](./simulation/README.md) for detailed architecture, test instructions, and scenario reference.
