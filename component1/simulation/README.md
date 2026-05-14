# Component 1 — Simulation Framework

## Overview

This simulation framework generates synthetic Kubernetes cluster observations that follow the **canonical schema** defined in [`../../common schema/SCHEMA.md`](../../common%20schema/SCHEMA.md).

The simulator produces realistic **NormalizedObservation** objects — the exact data structure Component 1 would emit after collecting raw metrics from a real K8s cluster. This enables:
- ✅ **Offline testing** of Component 2 playbooks without needing a real cluster
- ✅ **Deterministic fault injection** to validate root cause analysis
- ✅ **Schema contract validation** between Component 1 and Component 2
- ✅ **Latency/throughput benchmarking** of the pipeline

---

## What It Does

### High-Level Flow

```
┌──────────────────┐
│  ClusterState    │  ← mutable state (pods, nodes, services, PVCs)
│  (raw metrics)   │
└────────┬─────────┘
         │
         ├─→ scenarios/     ← inject faults (e.g., OOM, CPU contention)
         │    (apply_*)
         │
         ├─→ generators/    ← add realistic drift & noise each tick
         │    (tick_*)
         │
         └─→ normalizer.py  ← convert raw → canonical schema
              (normalize)
              │
              ↓
         NormalizedObservation (dict)
              │
              ↓
         output/observation_writer.py
              │
              ↓
         observations.ndjson  ← Component 2 reads this
```

### What's Simulated

| Component | What's Tracked | Metrics |
|-----------|----------------|---------|
| **Pod** | CPU, Memory, Probes, Restarts, Network, Storage | `pod.cpu.usage_percent`, `pod.memory.working_set_bytes`, `pod.probe.latency_ms`, etc. |
| **Node** | CPU, Memory, Storage/IO, Network, DNS | `node.cpu.usage_percent`, `node.memory.available_bytes`, `node.net.tcp_retrans_rate`, etc. |
| **Service** | Replica readiness, latency (p50/p99), error rate, QPS | `service.ready_replicas`, `service.latency_p99_ms`, `service.error_rate` |
| **PVC** | Phase, pending duration | `pvc.phase`, `pvc.pending_duration_ms` |
| **Events** | Pod restarts, OOM kills, evictions, deployment changes | pod_restart, oom_kill, eviction, deploy, scale, node_condition |

---

## Architecture

### Core Files

#### 1. **cluster_state.py**
Defines the **mutable world state** — all raw metrics as they would come from Prometheus, cAdvisor, Kubelet, K8s API.

```python
@dataclass
class PodState:
    pod_id: str                      # "default/redis-0"
    cpu_usage_millicores: float      # 50.0 (raw from cAdvisor)
    cpu_throttled_periods: int       # cumulative counter
    memory_working_set_bytes: int    # 80 MiB (raw from cAdvisor)
    probe_latency_ms: int            # probe execution time
    restart_count: int               # cumulative restarts
    # ... etc (see full class)

@dataclass
class NodeState:
    cpu_usage_percent: float         # aggregated node CPU%
    memory_available_bytes: int      # from node-exporter
    tcp_retrans_segs: int            # cumulative
    # ... etc

@dataclass
class ClusterState:
    pods: List[PodState]
    node: NodeState
    services: List[ServiceState]
    pvcs: List[PVCState]
    tick: int                        # observation number
    timestamp_ms: int                # wall clock
```

#### 2. **normalizer.py**
Maps **raw ClusterState** → **canonical NormalizedObservation** dict.

This is **the core of Component 1's job**: every field name, type, unit must match `SCHEMA.md` exactly.

```python
class Normalizer:
    def normalize(state: ClusterState) -> Dict[str, Any]:
        # e.g., converts:
        #   pod.cpu_throttled_periods / pod.cpu_total_periods
        # → 
        #   "pod.cpu.throttle_ratio": 0.35 (0-1 normalized)
        #
        # Returns: { "pod.id": "...", "pod.cpu.usage_percent": 10.0, ... }
```

#### 3. **generators/** — Realistic Metric Drift
Each tick (30s observation window), generators add noise and compute aggregates:

- **pod_generator.py**: Jitter CPU/memory values, accumulate throttle periods, compute probe latency
- **node_generator.py**: Aggregate pod metrics → node-level metrics, compute PSI signals
- **service_generator.py**: Compute ready replicas, error rate, latency percentiles from pod states

```python
def tick_pods(state: ClusterState):
    # Add ±5-10% relative Gaussian noise to CPU, memory
    # Accumulate CFS throttle periods based on fault_intensity
    # Trigger OOM events if memory > limit
    # Update probe latency and failures
```

#### 4. **scenarios/** — Fault Injection Patterns
Each scenario file defines how a particular failure unfolds over time:

| Scenario | What It Simulates | Time Stages |
|----------|-----------------|-------------|
| **baseline.py** | Healthy cluster (no faults) | Constant baseline |
| **oom_cascade.py** | Memory leak → OOMKilled → node evictions | Phases: leak → hit → evict |
| **cpu_contention.py** | Shared-core CPU throttling → probe timeout → restart | Phases: rise → throttle → timeout |
| **probe_cascade.py** | Memory pressure → probe latency → probe failure → crash loop | Phases: memory rise → latency → failures → restarts |
| **grpc_degradation.py** | Network packet loss → gRPC degradation | Phases: normal → loss → degradation |
| **storage_saturation.py** | PVC usage grows → space exhausted → attachment errors | Phases: grow → saturate → fail |

**Example: oom_cascade.py**
```python
def apply(state: ClusterState, tick: int, total_ticks: int):
    progress = tick / total_ticks  # 0.0 -> 1.0
    
    if progress < 0.2:      # Phase 1: healthy
        pass
    elif progress < 0.5:    # Phase 2: memory leak (60% -> 100%)
        pod.memory_working_set_bytes = int(limit * (0.60 + progress * 0.40))
    elif progress < 0.65:   # Phase 3: OOM hit
        pod.memory_oom_events += 1
        state.add_event("oom_kill", pod.pod_id, "error", ...)
    else:                   # Phase 4: node pressure, evict others
        state.node.memory_available_bytes = ...  # low
        state.add_event("eviction", other_pod.pod_id, ...)
```

#### 5. **output/observation_writer.py**
Serializes NormalizedObservation dicts to **NDJSON** (newline-delimited JSON):

```
{"tenant_id": "tenant-sim-001", "cluster_name": "sim-cluster", "timestamp_ms": 1715708400000, "pod": [...], "node": {...}, ...}
{"tenant_id": "tenant-sim-001", "cluster_name": "sim-cluster", "timestamp_ms": 1715708430000, "pod": [...], "node": {...}, ...}
...
```

Each line is one observation (ready for Component 2 ingestion).

---

## Test Run Instructions

### Prerequisites

```bash
pip install -r requirements.txt
# or
pip install numpy PyYAML
```

### Create a Simple Test Runner

Create a file **`test_run.py`** at the simulation root:

```python
"""
test_run.py
Minimal test runner to validate the simulation end-to-end.
"""
import time
from cluster_state import ClusterState, PodState, NodeState, ServiceState
from normalizer import Normalizer
from generators.pod_generator import tick_pods
from generators.node_generator import tick_node
from generators.service_generator import tick_services
from output.observation_writer import ObservationWriter
from scenarios import baseline  # choose a scenario


def setup_cluster():
    """Initialize a simple cluster for testing."""
    state = ClusterState(
        tenant_id="tenant-sim-001",
        cluster_name="sim-cluster-test",
        tick=0,
    )
    
    # Add a few pods
    state.pods = [
        PodState(
            pod_id="default/redis-0",
            namespace="default",
            pod_name="redis-0",
            node_name="node-1",
            service="redis",
            labels={"app": "redis", "tier": "backend"},
        ),
        PodState(
            pod_id="default/backend-1",
            namespace="default",
            pod_name="backend-1",
            node_name="node-1",
            service="backend",
            labels={"app": "backend", "tier": "service"},
        ),
        PodState(
            pod_id="default/frontend-1",
            namespace="default",
            pod_name="frontend-1",
            node_name="node-1",
            service="frontend",
            labels={"app": "frontend", "tier": "web"},
        ),
    ]
    
    # Add a service
    state.services = [
        ServiceState(
            service_id="default/redis",
            namespace="default",
            service_name="redis",
            ready_replicas=1,
            desired_replicas=1,
        ),
        ServiceState(
            service_id="default/backend",
            namespace="default",
            service_name="backend",
            ready_replicas=1,
            desired_replicas=1,
        ),
    ]
    
    return state


def run_simulation(scenario_module, num_ticks: int = 100, output_file: str = "observations.ndjson"):
    """Run the simulation for num_ticks observations."""
    state = setup_cluster()
    normalizer = Normalizer()
    
    with ObservationWriter(output_file) as writer:
        for tick in range(num_ticks):
            state.tick = tick
            
            # 1. Apply scenario fault injection
            scenario_module.apply(state, tick, num_ticks)
            
            # 2. Generate realistic metric drift
            tick_pods(state)
            tick_node(state)
            tick_services(state)
            
            # 3. Normalize to canonical schema
            events = state.flush_events()
            observation = normalizer.normalize(state, events)
            
            # 4. Write observation
            writer.write(observation)
            
            if (tick + 1) % 10 == 0:
                print(f"✓ Tick {tick + 1}/{num_ticks} — {writer.observations_written} observations written")
    
    print(f"\n✅ Simulation complete!")
    print(f"   Output: {output_file}")
    print(f"   Total observations: {writer.observations_written}")
    return output_file


if __name__ == "__main__":
    # Run baseline scenario
    print("Starting simulation (baseline scenario)...")
    run_simulation(baseline, num_ticks=100, output_file="observations_baseline.ndjson")
    
    # Optional: run other scenarios
    # from scenarios import oom_cascade, cpu_contention, probe_cascade
    # run_simulation(oom_cascade, num_ticks=100, output_file="observations_oom.ndjson")
    # run_simulation(cpu_contention, num_ticks=100, output_file="observations_cpu.ndjson")
```

### Run the Test

```bash
cd component1/simulation
python test_run.py
```

**Expected Output:**
```
Starting simulation (baseline scenario)...
✓ Tick 10/100 — 10 observations written
✓ Tick 20/100 — 20 observations written
✓ Tick 30/100 — 30 observations written
...
✓ Tick 100/100 — 100 observations written

✅ Simulation complete!
   Output: observations_baseline.ndjson
   Total observations: 100
```

### Inspect the Output

```bash
# View first observation (pretty-printed)
head -1 observations_baseline.ndjson | python -m json.tool

# View line count
wc -l observations_baseline.ndjson
```

**Sample observation (first 5 fields):**
```json
{
  "tenant_id": "tenant-sim-001",
  "cluster_name": "sim-cluster-test",
  "timestamp_ms": 1715708400000,
  "capability.has_kubernetes_api": true,
  "capability.has_prometheus": true,
  "pod.id": "default/redis-0",
  "pod.namespace": "default",
  "pod.phase": "Running",
  "pod.cpu.usage_percent": 8.5,
  "pod.cpu.throttle_ratio": 0.0,
  "pod.memory.working_set_bytes": 83886080,
  "pod.memory.working_set_pct": 31.25,
  "pod.probe.latency_ms": 5,
  "pod.probe.consecutive_failures": 0,
  ...
}
```

---

## Validation Checklist

After running the simulation, verify:

### ✅ Schema Compliance
- [ ] Every field in the NDJSON output matches a field in `SCHEMA.md` Part A
- [ ] No invented field names (e.g., `pod_cpu_usage` should be `pod.cpu.usage_percent`)
- [ ] All units match (e.g., memory in bytes, CPU in %, time in ms, rates in per-second)

### ✅ Fault Injection
- For **OOM scenario**: Check that `pod.memory.oom_events` increments, events include `oom_kill`
- For **CPU contention**: Check that `pod.cpu.throttle_ratio` rises, probe latency increases
- For **Probe cascade**: Check that probe failures precede restarts
- For **Network degradation**: Check that packet drop rates rise

### ✅ Metric Realism
- [ ] Pod metrics have jitter (±5-10% noise) — not constant
- [ ] Node aggregates reflect pod states (e.g., CPU% rises when pods use more CPU)
- [ ] Service ready_replicas reflects pod phase and probe status
- [ ] Events are time-ordered and causally coherent

### ✅ Data Flow
- [ ] NormalizedObservations are emitted once per tick
- [ ] Capability flags are set (all True for simulation)
- [ ] Timestamps increment by 30s each tick
- [ ] Cumulative counters (e.g., restart_count) only increase

---

## Scenario Details

### baseline.py
**Status**: ✅ Healthy cluster  
**Use Case**: Calibration, baseline for comparison  
**What to Expect**:
- All pods in Running phase with low probe failure
- No OOM/eviction events
- Metric values near defaults with jitter only

### oom_cascade.py
**Status**: 🔴 Memory leak → OOMKilled → evictions  
**Use Case**: Test OOM-Cascade playbook  
**Phases**:
1. Ticks 0-20%: Healthy
2. Ticks 20-50%: Memory leak (WSS 60% → 100% of limit)
3. Ticks 50-65%: OOM hit (pod killed with exit code 137)
4. Ticks 65-100%: Node memory pressure → evict other pods

**Key Signals**:
- `pod.memory.oom_events` increments
- `pod.last_terminated_reason` = "OOMKilled"
- `node.memory.available_pct` drops
- `event.type` includes "oom_kill", "eviction"

### cpu_contention.py
**Status**: 🟡 CPU throttling → latency → probe timeout  
**Use Case**: Test CPU-Contention playbook  
**Phases**:
1. Ticks 0-20%: Healthy
2. Ticks 20-60%: Throttle ratio rises (5% → 70%), CPU usage climbs
3. Ticks 60-100%: Severe throttling, probe latency > 2000ms → failures

**Key Signals**:
- `pod.cpu.throttle_ratio` rises
- `pod.probe.latency_ms` approaches/exceeds 2000
- `service.latency_p99_ms` increases
- Probe failures logged in events

### probe_cascade.py
**Status**: 🟡 Memory pressure → probe latency → failures → restart loop  
**Use Case**: Test Probe-Cascade playbook  
**Phases**:
1. Ticks 0-20%: Healthy
2. Ticks 20-50%: Memory creeps (80% → 98% of limit)
3. Ticks 50-75%: Probe latency spikes (300ms → 2100ms)
4. Ticks 75-100%: Probe fails → restarts (crash loop begins)

**Key Signals**:
- `pod.memory.working_set_pct` rises
- `pod.probe.latency_ms` exceeds 2000
- `pod.probe.consecutive_failures` increments
- `pod.restart_delta` increases

### grpc_degradation.py
**Status**: 🔴 Network packet loss → gRPC degradation  
**Use Case**: Test gRPC-Degradation playbook  
**What to Expect**:
- `pod.net.rx_drop_rate` / `pod.net.tx_drop_rate` rises
- `service.error_rate` increases
- Service latency p99 climbs

### storage_saturation.py
**Status**: 🟡 PVC space exhausted  
**Use Case**: Test Storage-Saturation playbook  
**What to Expect**:
- `pod.storage.used_pct` approaches 100%
- `pvc.phase` may transition from Bound → (stays Bound, but pending_attach_ms rises)
- Storage-related events emitted

---

## Integration with Component 2

Once observations are generated:

1. **Feed to Component 2**: Copy `observations.ndjson` to Component 2's input directory
2. **Component 2 Processing**:
   - Reads each line as a `NormalizedObservation`
   - Extracts X features (pod/node/service metrics)
   - Runs playbooks (OOM-Cascade, CPU-Contention, etc.)
   - Emits `PlaybookFiringEvent` objects
3. **Validation**: Verify that playbook firing aligns with injected faults
   - OOM scenario → OOM-Cascade playbook fires
   - CPU scenario → CPU-Contention playbook fires
   - Etc.

---

## Extending the Simulation

### Add a New Pod Type
Edit `test_run.py` `setup_cluster()`:
```python
state.pods.append(PodState(
    pod_id="default/my-service-0",
    namespace="default",
    pod_name="my-service-0",
    node_name="node-1",
    service="my-service",
    labels={"app": "my-service", "tier": "custom"},
    cpu_limit_millicores=1000.0,  # 1 core
    memory_limit_bytes=512 * 1024 * 1024,  # 512 MiB
))
```

### Add a New Scenario
Create `scenarios/my_fault.py`:
```python
def apply(state: ClusterState, tick: int, total_ticks: int):
    progress = tick / total_ticks
    
    target = next((p for p in state.pods if p.service == "my-service"), None)
    if not target:
        return
    
    # Inject your fault
    if progress < 0.5:
        target.cpu_usage_millicores = target.cpu_limit_millicores * 0.2
    else:
        target.cpu_usage_millicores = target.cpu_limit_millicores * 0.9
```

Then run:
```python
from scenarios import my_fault
run_simulation(my_fault, num_ticks=100)
```

---

## Troubleshooting

### Issue: ImportError: No module named 'numpy'
**Solution:**
```bash
pip install numpy PyYAML
```

### Issue: NDJSON file is empty
**Solution:** Check that observations are being written. Add debug print in `test_run.py`:
```python
if tick % 10 == 0:
    print(f"Tick {tick}: observation keys = {list(observation.keys())[:5]}")
```

### Issue: Observations have NaN or inf values
**Solution:** Check that jitter functions clamp values. The generators use `max()` and `min()` to prevent negative/invalid values.

---

## Files at a Glance

```
component1/simulation/
├── README.md                        ← You are here
├── requirements.txt                 ← numpy, PyYAML
├── cluster_state.py                 ← Mutable state (raw metrics)
├── normalizer.py                    ← Raw → canonical schema
├── test_run.py                      ← Minimal runner (create this)
├── generators/
│   ├── __init__.py
│   ├── pod_generator.py             ← Add jitter, compute throttle
│   ├── node_generator.py            ← Aggregate pod metrics
│   └── service_generator.py         ← Compute service metrics
├── scenarios/
│   ├── __init__.py
│   ├── baseline.py                  ← No faults
│   ├── oom_cascade.py               ← Memory leak → OOM
│   ├── cpu_contention.py            ← CPU throttling
│   ├── probe_cascade.py             ← Memory → probe failure
│   ├── grpc_degradation.py          ← Network packet loss
│   └── storage_saturation.py        ← PVC space exhausted
└── output/
    ├── __init__.py
    └── observation_writer.py        ← NDJSON serialization
```

---

## Summary

✅ **This simulation is legitimate** and follows the Component 1 contract:
- Generates realistic K8s metrics with proper units and ranges
- Normalizes to the canonical schema (no invented fields)
- Outputs NormalizedObservation in NDJSON format
- Supports deterministic fault injection for testing

✅ **What it enables**:
- Offline Component 2 testing without a real cluster
- Validation that Component 2 playbooks fire correctly
- Schema contract verification
- Performance benchmarking

✅ **To test it**: Run `python test_run.py` to generate observations.ndjson with 100 observations in baseline scenario. Verify using `head observations_baseline.ndjson | python -m json.tool`.
