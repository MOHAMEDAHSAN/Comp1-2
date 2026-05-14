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
