# Component 1 & 2: Implementation Guide
## Data Ingestion & Normalization + Statistical Forecasting Engine

---

## 📋 EXECUTIVE OVERVIEW

You're building two interconnected components that form the **data pipeline foundation** of the system:

- **Component 1** (Ingestion & Normalization): Customer-side agent that collects, normalizes, and securely transmits observability data
- **Component 2** (Statistical Forecasting): Backend service that applies statistical methods to predict failure modes using playbook-based detection

**Data flow**: Kubernetes Cluster → Component 1 Agent → Component 2 Engine → Predictions → Reasoning Layer

---

## 🏗️ COMPONENT 1: DATA INGESTION & NORMALIZATION PLANE

### What It Does

A **lightweight customer-side agent** that runs in the Kubernetes cluster as a DaemonSet (per-node) + Deployment (collection/forwarding). It bridges the customer's heterogeneous data sources to the SaaS backend.

### Core Responsibilities

#### 1.1 **Schema Normalization** (Canonical Form Conversion)
   - **Problem**: Each customer has different metric names, labels, scrape intervals, data formats
   - **Solution**: Agent inspects available data sources and maps them to canonical schema
   - **Output**: Standardized observation model
   - **Key Feature**: Capability degradation reporting
     - Example: "Full storage analysis requires metrics X, Y, Z; X and Y present, Z missing → degraded mode"
   - **Implementation Approach**:
     - Define canonical schema (TypeScript/Go interfaces)
     - Build mapper layer (source format → canonical)
     - Track capability flags per data type
     - Expose mapping UI for custom metric names

#### 1.2 **Observation Collection** (Multi-Source Data Scraping)
   - **Required minimum**: Kubernetes API
   - **Recommended tier**: Service mesh telemetry + custom metrics
   - **Premium tier**: eBPF kernel-level observation
   
   **Data sources to collect**:
   - Kubernetes API (topology, events, pod state)
   - Prometheus or equivalent (metrics)
   - Log aggregators (log streams)
   - Kubelet (pod/node state, resource usage)
   - Service mesh (traffic, latency, errors)
   - eBPF programs (advanced - premium)
   
   **Implementation approach**:
   - Modular source adapters (pluggable)
   - Configurable scrape intervals per source
   - Deduplication and aggregation logic
   - Buffer/batching before forwarding

#### 1.3 **Secure Transport & Tenancy Isolation**
   - **Security**: Authenticated HTTPS channel to backend
   - **Tenancy**: Each customer isolated (API token, namespace scoping)
   - **Versioning**: Handle backward compatibility as schema evolves
   - **Control**: Customer can enable/disable specific data streams
   
   **Implementation approach**:
   - mTLS or API token authentication
   - Envelope encryption for sensitive data
   - Batch/streaming protocol (gRPC or custom)
   - Retry logic with exponential backoff

### Architecture Pattern

```
┌─ DaemonSet (Per-Node)
│  ├─ kubelet observer
│  ├─ node-level metrics
│  └─ local data forwarding
│
└─ Deployment (Cluster-wide Coordination)
   ├─ API server observer
   ├─ Prometheus scraper
   ├─ Log aggregator client
   ├─ Schema normalizer
   └─ Secure transport handler
```

### Tech Stack Recommendations

- **Language**: Go (for agent) - lightweight, cross-platform, Kubernetes-native
- **Framework**: Kubernetes client-go + informers
- **Serialization**: Protocol Buffers (for compact, versioned data)
- **Transport**: gRPC (for efficient streaming) or HTTP/2
- **Config**: YAML (Helm chart for deployment)

### Step-by-Step Build Plan

**Phase 1: Foundation (Week 1)**
1. Define canonical schema (proto files)
2. Build Kubernetes client wrapper (API observer)
3. Implement basic topology scraper (pods, services, nodes)
4. Create data models and structures

**Phase 2: Multi-source Collection (Week 2)**
1. Prometheus metrics collection adapter
2. Log stream collection adapter
3. Kubelet metrics adapter
4. Service mesh telemetry adapter (optional for v1)

**Phase 3: Normalization & Mapping (Week 3)**
1. Capability detection logic
2. Schema mapper (source → canonical)
3. Custom metric name mapping
4. Degradation reporting

**Phase 4: Transport & Deployment (Week 4)**
1. Secure transport layer (mTLS/auth)
2. Batch/stream protocol implementation
3. Helm chart for DaemonSet + Deployment
4. Configuration schema

---

## 🔬 COMPONENT 2: STATISTICAL FORECASTING ENGINE

### What It Does

A **backend service** that receives normalized data from Component 1 and applies statistical methods to predict failure-mode occurrences. It monitors selected variables from failure-mode playbooks and fires predictions.

### Core Responsibilities

#### 2.1 **Baseline Calibration**
   - **Purpose**: Establish normal behavior for each metric per customer
   - **Method**: Pooled-σ (pooled standard deviation across multiple baseline windows)
   - **Triggers for reset**: Cluster events, configuration changes, deploys
   - **Implementation**:
     - Sliding window baseline computation
     - Per-metric baselines scoped to topology (pod type, namespace, etc.)
     - Drift detection (baseline stability monitoring)
     - Mutation reset logic (clear baseline after cluster changes)

#### 2.2 **Detection Algorithms**
   - **Time-series forecasting**: ARIMA, exponential smoothing
   - **Statistical inference**: Z-score, percentile deviation, hypothesis testing
   - **Causal inference (bounded)**: Constraint-based methods using domain knowledge
   
   **Playbook structure**:
   ```
   Playbook {
     id: "probe-cascade"
     selected_variables: [memory_usage, probe_latency, pod_restarts]
     detection_algorithm: ConvolvedTimeSeriesDetector
     pattern_signature: ProbePattern
     recommended_action: "Increase memory limits or reduce probe frequency"
   }
   ```

#### 2.3 **Playbook Management**
   - **V1 Set** (5-10 playbooks):
     - Probe-cascade (memory pressure → probe failures → kills)
     - CPU contention (workload coupling on shared cores)
     - OOM cascade (memory pressure propagation)
     - gRPC degradation (network impairment effects)
     - Storage queue saturation (I/O bottleneck)
   
   - **Playbook responsibilities**:
     - Define which metrics matter (selected variables)
     - Specify detection algorithm + parameters
     - Calibrate thresholds per customer
     - Link to pattern library entries

#### 2.4 **Event Emission**
   - **Output**: `PlaybookFiringEvent`
   - **Contains**: Playbook ID, confidence score, affected nodes, selected variable values
   - **Delivery**: To reasoning layer (Component 3) as event stream
   - **Lifecycle**: Firing → Resolving → Resolved

### Playbook Deep Dive: Probe-Cascade Example

```
Name: Probe-Cascade Pattern Detection

Selected Variables:
  - Memory usage (% of requests)
  - Probe latency (p95, p99)
  - Pod restart count (rate)
  - Kubelet eviction events

Detection Algorithm:
  1. Compute memory baseline (pooled-σ)
  2. Detect memory pressure (> 3σ above baseline)
  3. Monitor probe latency spike correlating with memory
  4. Detect latency spike (> 2σ increase)
  5. Correlate probe failures with restart events
  6. If all three fire in sequence: emit PlaybookFiringEvent with confidence

Confidence Scoring:
  - All three conditions present: 0.9-1.0
  - Two conditions + patterns match: 0.7-0.8
  - One condition + strong pattern match: 0.5-0.6

Pattern Signature:
  - Duration: typically 30-90 seconds
  - Affected metrics: memory, latency, restarts
  - Log signatures: "Evicted", "probe failed", "container kill"
```

### Architecture Pattern

```
┌─ Data Ingestion Pipeline
│  └─ Receive normalized streams from Component 1
│
├─ Baseline Store
│  ├─ Per-metric per-topology baselines
│  └─ Drift monitoring
│
├─ Playbook Engines (Parallel)
│  ├─ Probe-cascade detector
│  ├─ CPU contention detector
│  ├─ OOM detector
│  ├─ gRPC detector
│  └─ Storage detector
│
├─ Event Emitter
│  └─ PlaybookFiringEvent stream to Component 3
│
└─ Admin Dashboard
   ├─ Playbook configuration
   ├─ Threshold tuning
   └─ Calibration status
```

### Tech Stack Recommendations

- **Language**: Python (ML-friendly) or Go (performance-focused)
- **Streaming**: Kafka or gRPC streaming for event delivery
- **State Store**: PostgreSQL (baselines, playbook configs) + Redis (live state)
- **Time-series library**: NumPy/Pandas (Python) or time-series crates (Rust)
- **Framework**: FastAPI (Python) or Axum (Rust) for admin API

### Step-by-Step Build Plan

**Phase 1: Foundation (Week 1)**
1. Define playbook data model (proto/OpenAPI)
2. Implement baseline store (schema, CRUD)
3. Build baseline calibration engine
4. Create event emission interface

**Phase 2: Detection Algorithms (Week 2)**
1. Implement pooled-σ baseline derivation
2. Build Z-score detector
3. Implement time-series deviation detector
4. Create confidence scoring logic

**Phase 3: Playbook Implementations (Week 3)**
1. Implement probe-cascade playbook
2. Implement CPU contention playbook
3. Implement OOM cascade playbook
4. Implement gRPC degradation playbook
5. Implement storage queue playbook

**Phase 4: Integration & Calibration (Week 4)**
1. Integrate event emission to Component 3
2. Build playbook configuration API
3. Implement online calibration (per-customer baseline tuning)
4. Create monitoring dashboard

---

## 🔌 COMPONENT 1 ↔ COMPONENT 2 INTERFACE

### Data Contract

```protobuf
// From Component 1 to Component 2
message NormalizedObservation {
  string tenant_id = 1;
  int64 timestamp_ms = 2;
  
  // Topology
  repeated PodMetrics pod_metrics = 3;
  repeated ServiceMetrics service_metrics = 4;
  repeated NodeMetrics node_metrics = 5;
  
  // Events
  repeated ClusterEvent events = 6;
  
  // Log stream pointers
  repeated LogEntry logs = 7;
}

// From Component 2 to Component 3
message PlaybookFiringEvent {
  string playbook_id = 1;
  string tenant_id = 2;
  int64 timestamp_ms = 3;
  float confidence = 4;
  
  repeated string affected_pod_ids = 5;
  map<string, double> selected_variable_values = 6;
  string reason = 7;
}
```

### Handoff Points

1. **Component 1 → Component 2**: HTTP/gRPC POST of NormalizedObservation batches
2. **Component 2 → Component 3**: Event stream (Kafka topic or gRPC subscribe)

---

## ⚙️ CONFIGURATION & DEPLOYMENT

### Component 1: Helm Chart Structure

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: kubernetes-agent

---
apiVersion: v1
kind: DaemonSet
metadata:
  name: kubernetes-agent-observer
  # Per-node observation

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kubernetes-agent-aggregator
  # Collection and forwarding
```

### Component 2: Environment Configuration

```yaml
# Config file or env vars
COMPONENT1_INGESTION_URL: https://component1.svc.cluster.local:443
BASELINE_WINDOW_HOURS: 24
BASELINE_RESET_EVENTS: ["deploy", "scale", "config_change"]
PLAYBOOKS_ENABLED: ["probe-cascade", "cpu-contention", "oom", "grpc", "storage"]
CONFIDENCE_THRESHOLD: 0.65
```

---

## 🧪 TESTING STRATEGY

### Component 1 Tests

**Unit**:
- Schema mapper (source → canonical)
- Capability detection
- Data deduplication

**Integration**:
- Scraping from mock Kubernetes API
- Transport to mock backend
- Tenancy isolation

**E2E**:
- Deploy on actual k8s cluster
- Verify data reaches backend
- Validate schema compliance

### Component 2 Tests

**Unit**:
- Baseline calibration (known data)
- Detection algorithms (synthetic anomalies)
- Playbook firing (test case data)

**Integration**:
- Multi-playbook parallel firing
- Event emission to event stream
- Playbook parameter updates

**E2E**:
- Replay historical cluster data
- Verify expected playbooks fired
- Cross-check with manual analysis

---

## 📊 METRICS TO TRACK

### Component 1
- Data scrape latency (per source)
- Normalization success rate
- Capability degradation flags
- Bytes transmitted per interval
- Tenant isolation violations (audit)

### Component 2
- Baseline calibration coverage
- Playbook detection latency
- False positive rate per playbook
- Confidence score distribution
- Event emission throughput

---

## 🚀 IMPLEMENTATION SEQUENCE (Recommended)

```
Week 1: Component 1 - Foundation
  ├─ Canonical schema definition
  ├─ Kubernetes API scraper
  └─ Data models

Week 2: Component 1 - Multi-source Collection
  ├─ Prometheus adapter
  ├─ Kubelet metrics
  └─ Log stream adapter

Week 3: Component 1 - Normalization & Deployment
  ├─ Schema mapper
  ├─ Helm chart
  └─ E2E testing on testbed

Week 4: Component 2 - Foundation
  ├─ Baseline store (DB schema)
  ├─ Event model
  └─ Basic calibration

Week 5: Component 2 - Algorithms
  ├─ Pooled-σ implementation
  ├─ Detection algorithms
  └─ Confidence scoring

Week 6: Component 2 - Playbooks
  ├─ 5 playbooks implemented
  ├─ Calibration logic
  └─ Event emission

Week 7-8: Integration & Polish
  ├─ Component 1 ↔ Component 2 handoff
  ├─ End-to-end flow testing
  ├─ Performance optimization
  └─ Documentation
```

---

## 💡 KEY DESIGN DECISIONS

### Why Separate Components?

1. **Deployment flexibility**: Component 1 in customer environment, Component 2 on SaaS backend
2. **Scaling independently**: Component 2 can scale horizontally without touching customer infrastructure
3. **Security boundary**: Normalized data is the contract; customer's raw infrastructure details stay private
4. **Troubleshooting**: Clean separation makes debugging easier

### Why Playbook-Based Detection?

1. **Interpretability**: Each playbook is a self-contained, understandable failure mode
2. **Calibration**: Thresholds are per-playbook, easier to tune than global anomaly detection
3. **Extensibility**: New playbooks plug in without affecting others
4. **Traceability**: Evidence chain is clear ("playbook P fired because X, Y, Z")

### Why Pooled-σ for Baseline?

1. **Robustness**: Multiple windows reduce noise vs single-window stddev
2. **Adaptive**: Resets on cluster events, doesn't drift
3. **Simple**: Easy to understand, debug, and verify
4. **Domain-aligned**: Matches how humans reason about "normal" clusters

---

## ✅ DEFINITION OF DONE

### Component 1 Complete When:
- [ ] Scrapes all 5 data sources (API, Prometheus, Kubelet, Logs, optional mesh)
- [ ] Normalizes to canonical schema with <5% data loss
- [ ] Reports capability degradation accurately
- [ ] Transmits securely (mTLS/token auth)
- [ ] Helm chart deploys in under 2 minutes
- [ ] E2E test on live k8s cluster passes
- [ ] Handles 100+ pods without resource exhaustion

### Component 2 Complete When:
- [ ] Baseline calibration achieves <2% false positive rate on quiet clusters
- [ ] All 5 playbooks implemented and calibrated
- [ ] Playbook firing confidence correlates with manual analysis (>0.8 correlation)
- [ ] Event emission latency <500ms after anomaly detection
- [ ] Admin API for playbook config is live
- [ ] Scaling test: 1000s of concurrent playbook evaluations

---

## 📚 REFERENCE DOCUMENTS

- [High-Level Architecture](Architecture/High_level/High_level_design.md)
- [Component 1-2 SVG Diagram](component1_2_architecture.svg)
- [Pre-experimentation Data](Pre-experimentation/k8s-spike/consolidated_findings.md)

---

## 🤔 FREQUENTLY ASKED QUESTIONS

**Q: Should Component 1 be a Kubernetes operator or just a DaemonSet + Deployment?**
A: Just a DaemonSet + Deployment for v1. Operator pattern adds complexity; simple agents are easier to debug and update.

**Q: Can Component 2 make real-time decisions or send alerts?**
A: No, only emits events. Decision-making and alerts are Component 3 and 4's job.

**Q: What if a playbook misfires frequently?**
A: Adjust thresholds via admin API, or disable until better calibrated. Add to backlog for next playbook tuning cycle.

**Q: How do we handle multi-cluster scenarios?**
A: Out of scope for v1. Each customer-cluster pair is independent. Federated KG is future work (Component 3 scope).

**Q: What about eBPF observation?**
A: Premium tier. Implement basic K8s API + Prometheus first (v1). eBPF adds complexity and security implications.

