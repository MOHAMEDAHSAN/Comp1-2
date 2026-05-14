# Component 1 & 2: Quick Reference Guide
## One-Page Summary for Your Work

---

## 🎯 WHAT YOU'RE BUILDING

### Component 1: Data Ingestion & Normalization (Customer-side Agent)
**Runs in**: Customer's Kubernetes cluster (as DaemonSet + Deployment)
**Does**: Collects data from 5 sources → Normalizes to canonical schema → Sends securely to backend

**5 Data Sources**:
1. **Kubernetes API**: Pod/service topology, events
2. **Prometheus**: CPU, memory, network metrics
3. **Kubelet**: Node-level metrics, pod events, resource usage
4. **Logs**: Pod logs, error/crash patterns
5. **Service Mesh** (optional): Request latency, error rates

**Output**: `NormalizedObservation` (protobuf message with all metrics in canonical form)

### Component 2: Statistical Forecasting Engine (Backend Service)
**Runs on**: SaaS backend
**Does**: Receives normalized data → Calibrates baselines → Runs 5 failure-mode playbooks → Emits events

**5 Playbooks**:
1. **Probe-Cascade**: Memory pressure → Probe failures → Pod kills
2. **CPU Contention**: CPU spike → Latency spikes on co-located pods
3. **OOM Cascade**: Memory leak → Repeated OOM kills
4. **gRPC Degradation**: Network latency → gRPC failures
5. **Storage Queue Saturation**: PVC full → Write latency spike

**Output**: `PlaybookFiringEvent` (fired playbook with confidence score)

---

## 🔄 DATA FLOW

```
Customer Cluster → Component 1 Agent (normalization) → 
  → Secure Transport (gRPC over mTLS) → 
  → Component 2 Backend (detection) → 
  → Playbook Events → 
  → Component 3 (reasoning layer)
```

---

## 📋 COMPONENT 1 TECH STACK

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Go | Lightweight, K8s-native, easy distribution |
| Kubernetes Client | client-go | Official K8s library |
| Serialization | Protocol Buffers | Compact, versioned, efficient |
| Transport | gRPC | HTTP/2, streaming, efficient |
| Deployment | Helm | Industry standard for K8s |
| Container | Docker | Standard deployment |

**Key Responsibilities**:
- [ ] Scrape all 5 data sources in parallel
- [ ] Map custom metric names to canonical schema
- [ ] Track capability (what data sources available)
- [ ] Deduplicate events
- [ ] Batch and send securely (max 30s latency)
- [ ] Handle failures gracefully (local cache if backend down)

---

## 📋 COMPONENT 2 TECH STACK

| Layer | Choice | Why |
|-------|--------|-----|
| Language | Python or Go | ML-friendly (Python) or performance (Go) |
| Database | PostgreSQL | Baselines, playbook configs |
| Cache | Redis | Live state, deduplication |
| Time-Series | NumPy/Pandas or Rust time-series crate | Statistical computations |
| Web Framework | FastAPI (Python) / Axum (Go) | REST API for admin |
| Streaming | Kafka or gRPC | Event emission to Component 3 |

**Key Responsibilities**:
- [ ] Store normalized observations
- [ ] Compute pooled-σ baselines (multi-window stddev)
- [ ] Detect baseline violations using Z-scores
- [ ] Run 5 playbooks in parallel
- [ ] Score confidence for each playbook
- [ ] Emit events when playbook fires
- [ ] Provide admin API for tuning
- [ ] Handle per-customer baseline calibration

---

## 🏗️ ARCHITECTURE SUMMARY

### Component 1 Layers
```
Data Collection Layer
  ├─ K8s API adapter
  ├─ Prometheus adapter
  ├─ Kubelet adapter
  ├─ Log adapter
  └─ Service Mesh adapter
         ↓
Normalization Layer
  ├─ Capability detection
  ├─ Schema mapper (custom → canonical)
  ├─ Deduplicator
  └─ Aggregator
         ↓
Transport Layer
  ├─ Batcher
  ├─ Auth handler (mTLS/token)
  ├─ Retry logic
  └─ Protocol encoder (gRPC)
```

### Component 2 Layers
```
Data Ingestion
  ├─ Observation receiver
  ├─ Parser
  └─ Validator
        ↓
Baseline Calibration
  ├─ Time window manager
  ├─ Pooled-σ computation
  ├─ Drift detector
  └─ Reset logic (on cluster events)
        ↓
Detection Engines (Parallel)
  ├─ Probe-cascade detector
  ├─ CPU contention detector
  ├─ OOM cascade detector
  ├─ gRPC degradation detector
  └─ Storage queue detector
        ↓
Confidence & Emission
  ├─ Confidence calculator
  ├─ Playbook state tracker
  └─ Event builder → Kafka/gRPC
```

---

## 📊 KEY ALGORITHMS

### Pooled-σ Baseline Calibration (Component 2)

```python
# Input: 7 days of observations, split into 6-hour windows
# Output: baseline mean and stddev

windows = create_non_overlapping_windows(observations, 6_hours)

# For each window, compute mean & stddev
for window in windows:
    window.mean = average(window.values)
    window.stddev = std_dev(window.values)

# Compute overall statistics across windows
overall_mean = sum(w.mean * w.count for w in windows) / total_count

pooled_variance = sum(
    (w.count - 1) * w.stddev^2 + 
    w.count * (w.mean - overall_mean)^2
    for w in windows
) / (total_count - len(windows))

baseline_stddev = sqrt(pooled_variance)
```

**Why**: More robust than single-window stddev; reduces noise; adapts to customer's real patterns

### Playbook Detection (Component 2)

```python
# Pseudo-code for any playbook

confidence = 0.0
evidence = []

# Signal 1: Metric 1 anomalous?
z1 = (metric1 - baseline1.mean) / baseline1.stddev
if abs(z1) > 2.0:
    confidence += 0.25
    evidence.append(f"Signal 1: {z1:.2f}σ deviation")

# Signal 2: Metric 2 anomalous?
z2 = (metric2 - baseline2.mean) / baseline2.stddev
if abs(z2) > 2.5:
    confidence += 0.25
    evidence.append(f"Signal 2: {z2:.2f}σ deviation")

# ... repeat for all signals ...

# Temporal correlation?
if signals_follow_expected_sequence():
    confidence *= 1.2  # Boost confidence

return PlaybookFiringEvent(
    confidence=min(confidence, 1.0),
    reason=" | ".join(evidence)
)
```

---

## 🧪 SUCCESS CRITERIA

### Component 1
- ✅ Scrapes all 5 sources without blocking (<30s per cycle)
- ✅ Normalizes data with <5% loss
- ✅ Securely transmits (mTLS + tenant isolation)
- ✅ Helm chart deploys in <2 minutes
- ✅ Memory usage <500MB for 500+ pods
- ✅ E2E test passes on test cluster

### Component 2
- ✅ Baseline calibration <1% false positive on quiet clusters
- ✅ All 5 playbooks detect their target failure modes
- ✅ Detection latency <5 seconds
- ✅ Confidence scores correlate with ground truth
- ✅ Admin API fully functional
- ✅ 24-hour stability test passed

---

## 📁 FILE STRUCTURE (Final Deliverable)

```
Component 1 (Agent):
├─ proto/
│  └─ observability.proto
├─ cmd/agent/
│  ├─ main.go
│  ├─ sources/
│  │  ├─ kubernetes_source.go
│  │  ├─ prometheus_source.go
│  │  ├─ kubelet_source.go
│  │  ├─ log_source.go
│  │  └─ orchestrator.go
│  ├─ normalizer/
│  │  ├─ schema_normalizer.go
│  │  └─ deduplicator.go
│  ├─ transport/
│  │  └─ secure_transport.go
│  └─ config/
│     └─ config.go
├─ charts/kubernetes-agent/
│  ├─ Chart.yaml
│  ├─ values.yaml
│  └─ templates/
├─ test/
│  ├─ e2e_test.go
│  └─ integration_test.go
├─ Dockerfile
├─ go.mod
└─ go.sum

Component 2 (Backend):
├─ proto/
│  └─ forecasting.proto
├─ cmd/forecasting-engine/
│  └─ main.go
├─ internal/
│  ├─ store/
│  │  └─ baseline_store.go
│  ├─ calibration/
│  │  ├─ pooled_sigma.go
│  │  └─ online_calibration.go
│  ├─ detection/
│  │  ├─ detector.go
│  │  ├─ probe_cascade_detector.go
│  │  ├─ cpu_contention_detector.go
│  │  ├─ oom_detector.go
│  │  ├─ grpc_detector.go
│  │  ├─ storage_detector.go
│  │  └─ state_manager.go
│  ├─ ingestion/
│  │  └─ observation_handler.go
│  ├─ api/
│  │  ├─ admin_handler.go
│  │  └─ dashboard_handler.go
│  └─ events/
│     └─ event_emitter.go
├─ test/
│  ├─ component2_integration_test.go
│  └─ benchmark_test.go
├─ migrations/
│  └─ 001_baseline_schema.sql
├─ Dockerfile
├─ go.mod (or requirements.txt if Python)
└─ go.sum
```

---

## ⏱️ 8-WEEK TIMELINE AT A GLANCE

| Week | Component | Focus | Deliverable |
|------|-----------|-------|------------|
| 1 | 1 | Foundation | Proto schema, K8s client, topology discovery |
| 2 | 1 | Collection | Prometheus, Kubelet, Log adapters |
| 3 | 1 | Normalization | Schema mapper, capability detection, E2E test |
| 4 | 1 | Deployment | Helm chart, secure transport, integration |
| 5 | 2 | Foundation | Proto schema, baseline store, pooled-σ algorithm |
| 6 | 2 | Playbooks | All 5 detectors, confidence scoring, state mgmt |
| 7 | 2 | Admin | API, dashboard, online calibration |
| 8 | Both | Integration | E2E tests, performance benchmarks, documentation |

---

## 🔑 KEY DECISIONS

**Why separate Component 1 & 2?**
- Component 1 in customer cluster (security boundary)
- Component 2 on backend (shared, scaled infrastructure)
- Clean contract (normalized data) between them

**Why playbook-based detection?**
- Each playbook is a self-contained, interpretable failure mode
- Easier to calibrate, test, and extend
- Thresholds are playbook-specific, not global

**Why pooled-σ baseline?**
- Robust to noise (multiple windows)
- Adaptive (resets on cluster events)
- Simple to understand and debug

**Why gRPC for transport?**
- HTTP/2 streaming (efficient for batches)
- Bidirectional communication (future: server-side events)
- Protocol buffers (compact, versioned)

---

## ❓ FAQs QUICK ANSWERS

**Q: Can Component 1 work without Prometheus?**
A: Yes. Kubernetes API is required minimum. Prometheus is optional but recommended for full capability.

**Q: What if a playbook fires incorrectly?**
A: Adjust threshold via admin API, or disable temporarily. Add to backlog for tuning in next cycle.

**Q: How do we handle multi-cluster?**
A: Out of scope for v1. Each cluster gets its own Component 1 instance. Federation is future work (Component 3 scope).

**Q: What about machine learning models?**
A: Not in v1. We use statistical methods (baselines, Z-scores, causal inference on selected variables). ML models can be added later.

**Q: Is auto-remediation supported?**
A: No. Component 2 only detects and predicts. Component 3 reasons; operator decides and acts.

---

## 📚 DETAILED DOCUMENTATION

For deep dives, see:
- **COMPONENT_1_2_IMPLEMENTATION_GUIDE.md** - Full architecture & design
- **PLAYBOOK_SPECIFICATION_GUIDE.md** - Each playbook in detail
- **DEVELOPMENT_ROADMAP.md** - Week-by-week breakdown
- **component1_2_architecture.svg** - Visual architecture diagram

---

## 🚀 GETTING STARTED

1. **Read** this quick reference
2. **Read** the full implementation guide
3. **Review** the playbook specifications
4. **Follow** the development roadmap
5. **Reference** architecture diagrams
6. **Execute** week 1 plan
7. **Build** incrementally, test frequently

**You've got this!** 💪

