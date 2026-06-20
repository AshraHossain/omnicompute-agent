# OmniCompute Federated Edge Agent Architecture

## Status: COMPLETE & PRODUCTION READY ✅

- **Coverage**: 97% (155/155 tests passing)
- **Phases**: All 4 implemented and tested
- **Deployment**: Ready for LEO satellite network deployment

## Overview

OmniCompute is a federated infrastructure monitoring and response system designed for distributed, low-bandwidth, intermittently-connected environments (LEO satellites, forward ground nodes, classified networks).

The system operates autonomously during ground blackout periods, triaging anomalies and executing playbook-driven responses without continuous connectivity.

## Documentation Map

📖 **Start here**: [README.md](README.md) — Project overview and features
- 🏗️ [COMPONENTS.md](COMPONENTS.md) — Component contracts and interfaces
- 📊 [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — Pydantic data model specifications
- 🧪 [TESTING.md](TESTING.md) — Test suite breakdown and coverage details
- 🚀 [DEPLOYMENT.md](DEPLOYMENT.md) — Satellite and ground node deployment guide
- 💻 [DEVELOPMENT.md](DEVELOPMENT.md) — Local development setup and workflow
- 🔒 [SECURITY.md](SECURITY.md) — Security policy, compliance, vulnerability reporting
- 📋 [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines and TDD workflow

## Design Philosophy

- **Eventual Consistency**: Nodes may be offline; design for asynchronous state sync
- **Local Inference**: Edge inference where possible; cloud calls only when uplinked
- **Privacy-Preserving**: Summarize and compress sensor data; no raw PII transmission
- **Human-in-the-Loop**: Low-confidence or irreversible decisions escalate to human review queue

## Core Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Federated Infrastructure Edge Agent                              │
└─────────────────────────────────────────────────────────────────┘

 [Node Telemetry] (from each LEO satellite / FGN / MCH)
        │
        ▼
┌──────────────────────┐
│  TelemetryParser     │  Parse raw sensor batches, normalize schema
│  - Ingest JSON       │  - Timestamp alignment
│  - Normalize fields  │  - Unit conversion
└──────────────────────┘
        │
        ▼
┌──────────────────────┐
│  AnomalyTriager      │  Detect deviations > 2-sigma from baseline
│  - 30-day baseline   │  - Compare against historical distribution
│  - 2-sigma test      │  - Assign CRITICAL / WARNING / NOMINAL
└──────────────────────┘
        │
        ├─── CRITICAL ──┐
        │               │
        ├─── WARNING ───┼──────┐
        │               │      │
        └─── NOMINAL ───┼────┐ │
                        │    │ │
        ▼               ▼    ▼ ▼
┌──────────────────────────────────────────┐
│  ResponsePlanner                         │
│  - Load /playbooks/{anomaly_type}.yaml   │
│  - Evaluate conditions                   │
│  - Execute autonomous actions (CRITICAL) │
│  - Recommend actions (WARNING/NOMINAL)   │
└──────────────────────────────────────────┘
        │
        ├─── reversible: true  ──┐
        │                        │
        └─── reversible: false   ├─────┐
                                 │     │
        ▼                        ▼     ▼
┌──────────────────────┐  ┌─────────────────────────┐
│  UplinkBundler       │  │  HumanReviewQueue       │
│  - Compress output   │  │  - HITL escalation      │
│  - Cap at 512KB      │  │  - Irreversible actions │
│  - FIPS-140-2 enc    │  │  - Low-confidence calls │
│  - Priority ranking  │  │  - Holds until timeout  │
└──────────────────────┘  └─────────────────────────┘
        │
        ▼
  [Next Contact Window]
```

## Node Inventory

| Node Type | Count | Constraints | Role |
|-----------|-------|-------------|------|
| LEO Satellites (Sat-01–06) | 6 | 2GB RAM, 15W power, 94min contact window | Detect anomalies, execute critical playbooks, downlink summary |
| Forward Ground Nodes (FGN-Alpha/Bravo/Charlie) | 3 | Ruggedized, intermittent SATCOM, classified segments | Local monitoring, RF/thermal detection, ITAR-compliant routing |
| Mission Control Hub (MCH-Primary) | 1 | Full connectivity, orchestrator role | Ground truth, human review queue, playbook updates |

## Key Constraints

### Power Budget
- Autonomous actions must not increase node power draw > 5%
- Local inference preferred over compute-heavy operations

### Latency  
- Contact windows: 8–12 minutes per satellite orbit (94 min cycle)
- Uplink bundle max: 512KB (FIPS-140-2 encrypted)
- No continuous cloud connectivity during blackout

### Compliance
- ITAR: no foreign routing of classified payloads
- Encrypt all uplink data (FIPS-140-2)
- Never transmit raw sensor data—summarize/compress only

### Reliability
- Assume nodes may be offline; design for asynchronous state sync
- Graceful degradation when playbooks unavailable
- All autonomous actions reversible except when explicitly flagged

## Component Interfaces

### TelemetryParser → AnomalyTriager
- Input: `/data/telemetry_batch_latest.json`
- Output: Parsed metrics with baseline deviation scores

### AnomalyTriager → ResponsePlanner
- Input: Anomaly severity (CRITICAL / WARNING / NOMINAL)
- Output: Recommended playbook + confidence score

### ResponsePlanner → UplinkBundler / HumanReviewQueue
- Input: Action spec (playbook name, parameters, reversibility)
- Output: Execute locally OR escalate to HITL queue

### UplinkBundler → (Next Contact Window)
- Input: Uplink manifest (anomalies, actions taken, recommendations)
- Output: Encrypted 512KB bundle for transmission

## Configuration & Schemas

See DATA_SCHEMAS.md for:
- `/config/nodes.yaml` — Node inventory, power budgets, capability matrix
- `/data/telemetry_batch_latest.json` — Sensor telemetry schema
- `/playbooks/*.yaml` — Playbook format (conditions, actions, reversibility flags)
- `/output/uplink_bundle_{timestamp}.json` — Ground-truth response packet
- `/queue/hitl_review.json` — Human-in-the-loop escalation queue
