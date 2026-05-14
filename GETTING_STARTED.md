# Component 1: Getting Started - First Day Action Plan
## Your Complete Startup Guide

---

## 📖 START HERE

Welcome to **Component 1 (Data Ingestion & Normalization)** development!

This document walks you through **what to do today** (and this week) to get ready for development.

---

## 🎯 TODAY'S GOALS (May 13, 2026)

By end of today:
- [ ] Environment setup verified
- [ ] Team coordination established
- [ ] Component 2 requirements form sent
- [ ] Week 1 sprint planned

**Estimated time**: 2-3 hours (mostly waiting on Component 2 response)

---

## ✅ STEP 1: RUN PREFLIGHT CHECKLIST (30 minutes)

**Read**: [PREFLIGHT_CHECKLIST.md](PREFLIGHT_CHECKLIST.md)

This validates that your system is ready. It checks:
- ✅ Go, Docker, Helm, kubectl installed
- ✅ Project structure correct
- ✅ Dependencies resolved
- ✅ Proto schema compiles
- ✅ Build works

**Action**: Follow checklist, check off each item as you go.

**If anything fails**: Don't continue; fix it using the troubleshooting section in PREFLIGHT_CHECKLIST.md

---

## 📋 STEP 2: REVIEW COMPONENT 1 OVERVIEW (20 minutes)

**Read**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

This gives you a high-level understanding of:
- What Component 1 does
- Architecture layers
- Tech stack decisions
- Success criteria

**Key takeaway**: 
> Component 1 is an **agent that runs in the customer's cluster** and collects data from 5 sources, normalizes it, and sends it securely to Component 2.

---

## 🤝 STEP 3: COORDINATE WITH COMPONENT 2 TEAM (30 minutes)

**Send them**: [COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md](COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md)

This document has:
1. **What Component 1 must deliver** (Tier 1, 2, 3 requirements)
2. **Validation tests** Component 2 will run
3. **Handoff meeting checklist**

**Ask Component 2 team to fill out**:
```
COMPONENT 2 REQUIREMENTS FORM (see in HANDOFF_CHECKLIST.md):

Playbook 1: [name]
Required Metrics:
  [ ] [metric_name] - source: [K8s API / Prometheus / Kubelet / Logs]
  [ ] [metric_name] - source: [...]

[Repeat for each of their 5 playbooks]
```

**Timeline**: 
- Today: Send them the form
- Tomorrow-Wednesday: They fill it out
- Thursday: Review together

---

## 📚 STEP 4: UNDERSTAND DATA CONTRACT (30 minutes)

**Read**: [proto/observability.proto](proto/observability.proto)

This is the **interface between Component 1 and Component 2**. It defines:
- What data Component 1 sends
- What fields are required
- What fields are optional
- What capability flags mean

**Key takeaway**:
- `NormalizedObservation` = the message sent every ~30 seconds
- Contains: pod metrics, service metrics, node metrics, events, capability flags
- Every field has a comment explaining its purpose

**Don't memorize this**; just understand the structure.

---

## 📅 STEP 5: REVIEW DEVELOPMENT ROADMAP (45 minutes)

**Read**: [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md)

Focus on:
1. **Week 1 section** - This is your first sprint
2. **Timeline overview** - 8 weeks total, 4 for Component 1
3. **Success criteria** - Know what "done" looks like

**Key week 1 deliverables**:
- Proto schema definition ✅ (already done!)
- Kubernetes API client
- Basic topology discovery
- Project CI/CD setup

---

## 💬 STEP 6: TEAM KICKOFF MEETING (60 minutes)

**Schedule**: Tomorrow morning (May 14)

**Attendees**: Component 1 team + Component 2 team lead

**Agenda**:
1. **Review proto schema** (10 min)
   - Walk through NormalizedObservation
   - Explain each field
   - Q&A

2. **Component 1 architecture overview** (15 min)
   - Show data flow: K8s API → Prometheus → Kubelet → Normalization → Transport
   - Explain why 5 sources needed
   - Q&A

3. **Component 2 requirements** (20 min)
   - Component 2 team presents their 5 playbooks
   - What metrics each playbook needs
   - Any custom requirements
   - Any concerns

4. **Handoff plan** (10 min)
   - When Component 1 will deliver data
   - How to test integration
   - What "done" looks like

5. **Week 1 sprint** (5 min)
   - Confirm starting tasks
   - Set daily sync time

---

## 📊 STEP 7: UNDERSTAND WHAT COMPONENT 2 NEEDS (This week)

Once Component 2 provides requirements, create a **"What We Must Build"** checklist:

**Example (template)**:
```markdown
# What Component 1 Must Deliver for Component 2

## Playbook 1: Probe-Cascade
Component 2 needs:
- [ ] Pod memory usage (%)
- [ ] Probe latency (milliseconds)
- [ ] Pod restart count
- [ ] Pod restart events (from logs or kubelet)
- [ ] Container OOM kill events

Data freshness: Max 60s staleness
Accuracy: Memory ±5%, latency ±10%

## Playbook 2: CPU Contention
Component 2 needs:
- [ ] Pod CPU usage (%)
- [ ] CPU throttle time
- [ ] Service latency (p99)
- [ ] Request timeout rate

...repeat for all 5 playbooks...
```

**Once you have this**: You know EXACTLY what to build in weeks 2-4.

---

## 🗺️ WEEK 1 AT A GLANCE

This is what Week 1 looks like (May 15-18):

### Monday (May 15) - Foundation & Setup
- Morning: Team standup + confirm requirements
- 📋 Initialize Go project (already started)
- 🔨 Create Kubernetes API client wrapper
- Write unit tests for K8s client
- End of day: K8s API client working

### Tuesday (May 16) - Topology Discovery
- 📦 Implement topology discovery (pods, services, nodes)
- 🧪 Test against local k8s cluster
- 📝 Document data structures
- End of day: Topology discovery working on test cluster

### Wednesday (May 17) - CI/CD & Setup
- 🐳 Docker build working
- 📦 Helm chart initial version
- 🔄 GitHub Actions CI setup
- 📋 Create Makefile for builds
- End of day: CI/CD pipeline working

### Thursday (May 18) - Integration & Review
- 🧪 E2E test: agent runs and collects data
- 📊 Integration with Component 2 (mock data first)
- 🔍 Code review + cleanup
- 📋 Update documentation
- End of week: Week 1 deliverables completed

---

## 📋 WEEK 1 SUCCESS CRITERIA

Component 1 Week 1 is **DONE** when:

- [ ] Proto schema final and agreed with Component 2
- [ ] Kubernetes API client successfully connects and reads topology
- [ ] Topology discovery script runs and prints discovered pods/services
- [ ] Project builds in Docker without errors
- [ ] Helm chart scaffold complete and deployable
- [ ] GitHub Actions CI passing on every commit
- [ ] Team understands Component 2's exact requirements
- [ ] Next week's tasks identified and planned

---

## 🚀 WEEK 2 PREVIEW

Once Week 1 done, Week 2 starts multi-source collection:
- Prometheus metrics adapter
- Kubelet metrics adapter
- Log stream adapter
- Orchestrate all sources

But don't worry about this yet; focus on Week 1.

---

## 📚 DOCUMENTATION MAP

Here's how all docs fit together:

```
QUICK_REFERENCE.md ← START if you want overview
    ↓
ENVIRONMENT_SETUP_GUIDE.md ← Follow this to set up computer
    ↓
PREFLIGHT_CHECKLIST.md ← Run this to verify everything works
    ↓
COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md ← Use this to coordinate with Component 2
    ↓
COMPONENT_1_2_IMPLEMENTATION_GUIDE.md ← Read for deep technical details
    ↓
DEVELOPMENT_ROADMAP.md ← Follow week-by-week for execution
    ↓
PLAYBOOK_SPECIFICATION_GUIDE.md ← Reference for what Component 2 needs
```

---

## 🎯 YOUR ACTION LIST (Ordered by Priority)

### Today (May 13):
1. [ ] Run PREFLIGHT_CHECKLIST.md completely
2. [ ] Read QUICK_REFERENCE.md
3. [ ] Read proto/observability.proto
4. [ ] Send COMPONENT1_COMPONENT2_HANDOFF_CHECKLIST.md to Component 2 team
5. [ ] Schedule kickoff meeting with Component 2

### Tomorrow (May 14):
1. [ ] Kickoff meeting with Component 2 (learn their requirements)
2. [ ] Create "What We Must Build" checklist based on their requirements
3. [ ] Review DEVELOPMENT_ROADMAP.md Week 1 section
4. [ ] Plan Monday's sprint with team

### Rest of Week 1 (May 15-18):
1. [ ] Follow DEVELOPMENT_ROADMAP.md Week 1 plan
2. [ ] Daily standups (15 min each)
3. [ ] Update "What We Must Build" as clarifications come
4. [ ] End-of-week sync with Component 2

---

## 💡 KEY PRINCIPLES

As you start development, keep these in mind:

### 1. **Proto Schema is Sacred**
The proto schema (data contract) must be perfect. Any changes later = hard coordination with Component 2. Get it right in Week 1.

### 2. **Test Against Real K8s Early**
Don't build just for mock data. Get real Kubernetes (minikube/kind) running ASAP. Test against it daily.

### 3. **Component 2 Requirements = Your North Star**
Everything you build should directly satisfy Component 2's requirements. If something doesn't serve them, don't build it.

### 4. **Incremental Development**
Don't try to build all 5 data sources at once. Do: K8s API → Prometheus → Kubelet. Test each one before moving to next.

### 5. **Integration Testing Matters**
Mock data is fine for unit tests. But E2E tests must use real observations flowing to Component 2. Start this in Week 4.

---

## ❓ COMMON QUESTIONS

**Q: When do we write code?**
A: After Week 1 kickoff meeting. Today is coordination. Code starts Monday afternoon after team alignment.

**Q: What if Component 2 requirements are vague?**
A: Ask them for specifics using the requirements form. Examples:
- "Do you need probe latency for every observation or aggregated?"
- "For restart count, do you want cumulative or rate?"
- "What's acceptable data freshness for CPU metrics?"

**Q: Can we start coding before all requirements are in?**
A: Yes! Start with K8s API client (definitely needed). Pause on other sources until you know if Component 2 needs them.

**Q: What if requirements conflict?**
A: Example: Component 2 wants latency data, but Prometheus isn't available.
- Don't try to solve. Escalate to team.
- Document in capability flags that latency unavailable.
- Component 2 adjusts their detection accordingly.

**Q: How often do we sync with Component 2?**
A: 
- Kickoff: Once (tomorrow)
- Daily: Check if new requirements or blockers
- Weekly: Full sync Thursday
- Integration: Full daily once we have data flowing

---

## 🎓 LEARNING RESOURCES

If you need to learn background:

**Kubernetes**:
- Official docs: https://kubernetes.io/docs/
- Kubernetes concepts: https://kubernetes.io/docs/concepts/

**Go**:
- Go by Example: https://gobyexample.com/
- Go client-go: https://github.com/kubernetes/client-go

**Protocol Buffers**:
- Proto basics: https://developers.google.com/protocol-buffers/docs/gotutorial

**gRPC**:
- gRPC Go: https://grpc.io/docs/languages/go/

**Helm**:
- Helm intro: https://helm.sh/docs/intro/

Don't need to master these today. Just know where to look if you hit a concept you're unfamiliar with.

---

## 🏁 END-OF-DAY CHECKLIST (Today)

By end of today, you should have:

- [ ] Environment verified (PREFLIGHT_CHECKLIST passed)
- [ ] Understanding of what Component 1 does (QUICK_REFERENCE read)
- [ ] Data contract understood (proto/observability.proto read)
- [ ] Component 2 requirements form sent
- [ ] Kickoff meeting scheduled
- [ ] Week 1 plan understood
- [ ] Team knows what to do tomorrow

---

## 📞 IF YOU GET STUCK

1. **Check the docs** - 90% of issues are in ENVIRONMENT_SETUP_GUIDE.md or PREFLIGHT_CHECKLIST.md
2. **Ask the team** - Daily standups are for questions
3. **Message Component 2 team** - Don't wait; ask for clarification NOW
4. **Escalate** - If truly blocked, tell the lead immediately

---

## 🚀 READY TO BEGIN?

Once you've completed this today:

✅ Tomorrow: Kickoff meeting  
✅ Monday-Thursday: Week 1 development (DEVELOPMENT_ROADMAP.md)  
✅ Friday: Review & celebrate Week 1 completion

**You've got this!** 💪

---

**Questions? Confusion? Ask in daily standup or ping the team.** 

Let's build something great! 🎯

