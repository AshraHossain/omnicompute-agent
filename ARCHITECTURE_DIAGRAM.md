# OmniCompute Architecture Diagram

**Visual system overview of the 4-phase pipeline**

---

## High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    LEO SATELLITE / GROUND NODE                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                     PHASE 1: INGESTION                          │  │
│  │                                                                  │  │
│  │  Telemetry Input                                               │  │
│  │  (sensor data, metrics)                                        │  │
│  │         ↓                                                       │  │
│  │  ┌──────────────────────────┐                                 │  │
│  │  │  TelemetryParser         │                                 │  │
│  │  │  - Normalize             │                                 │  │
│  │  │  - Validate              │                                 │  │
│  │  │  - Extract metrics       │                                 │  │
│  │  └──────────────────────────┘                                 │  │
│  │         ↓                                                       │  │
│  │  Normalized Telemetry                                          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              PHASE 2: ANOMALY DETECTION                         │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────┐   ┌──────────────────────────┐  │  │
│  │  │  BaselineCache           │   │  AnomalyTriager          │  │  │
│  │  │  - 30-day rolling stats   │   │  - Z-score calculation   │  │  │
│  │  │  - Mean, stddev          │   │  - Severity assignment   │  │  │
│  │  │  - Confidence decay      │   │  - Confidence scoring    │  │  │
│  │  └──────────────────────────┘   └──────────────────────────┘  │  │
│  │         ↓                               ↓                       │  │
│  │  Baseline Lookup ←─────────────────→ Anomalies                │  │
│  │                                                                  │  │
│  │  Output: {node_id, metric, z_score, severity, confidence}     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │           PHASE 3: DECISION & RESPONSE PLANNING                 │  │
│  │                                                                  │  │
│  │  Anomalies               Config                                 │  │
│  │       ↓                    ↓                                     │  │
│  │       └────→ ┌────────────────────────────┐                    │  │
│  │              │   ResponsePlanner          │                    │  │
│  │              │   - Match playbooks        │                    │  │
│  │              │   - Combine confidences    │                    │  │
│  │              │   - Apply modifiers        │                    │  │
│  │              │     (eclipse, degradation) │                    │  │
│  │              │   - Enforce power budget   │                    │  │
│  │              └────────────────────────────┘                    │  │
│  │                           ↓                                     │  │
│  │              Proposed Actions (ranked)                         │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────────────────────────┐             │  │
│  │  │  Confidence > 0.75?                          │             │  │
│  │  │  - YES (reversible): Execute autonomously    │             │  │
│  │  │  - YES (irreversible): Log and escalate      │             │  │
│  │  │  - NO: Queue for HITL review                 │             │  │
│  │  └──────────────────────────────────────────────┘             │  │
│  │                           ↓                                     │  │
│  │              Executed Actions + Escalations                     │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │         PHASE 4: BUNDLE & QUEUE MANAGEMENT                      │  │
│  │                                                                  │  │
│  │  ┌──────────────────────────┐   ┌──────────────────────────┐  │  │
│  │  │  HumanReviewQueue        │   │  UplinkBundler           │  │  │
│  │  │  - Max 100 items         │   │  - Gzip compression      │  │  │
│  │  │  - Trim low-risk when    │   │  - Fernet encryption     │  │  │
│  │  │    full                  │   │  - 512KB size limit      │  │  │
│  │  │  - 3-hour timeout        │   │  - Priority sorting      │  │  │
│  │  │  - Fallback execution    │   │                          │  │  │
│  │  └──────────────────────────┘   └──────────────────────────┘  │  │
│  │         ↓                               ↓                       │  │
│  │  Escalations               Uplink Bundle (encrypted)            │  │
│  │  (awaiting MCH decision)    (ready for transmission)            │  │
│  │                                                                  │  │
│  │  Output: /queue/hitl_review.json                               │  │
│  │  Output: /output/uplink_bundle_{timestamp}.json                │  │
│  │  Output: /logs/autonomous_actions.jsonl (audit trail)          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
Telemetry Batch (JSON)
        ↓
    ┌───────────────────────────────────┐
    │  TelemetryParser                  │
    │  (Phase 1)                        │
    │                                   │
    │  Input: raw telemetry             │
    │  Output: normalized telemetry     │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │  BaselineCache + AnomalyTriager   │
    │  (Phase 2)                        │
    │                                   │
    │  Input: normalized telemetry      │
    │  Input: 30-day baselines          │
    │  Output: anomalies (z-score, sev) │
    └───────────────────────────────────┘
        ↓
    ┌───────────────────────────────────┐
    │  ResponsePlanner                  │
    │  (Phase 3)                        │
    │                                   │
    │  Input: anomalies                 │
    │  Input: playbooks                 │
    │  Output: actions (ranked)         │
    └───────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────┐
    │  Decision Tree:                         │
    │  - Confidence > 0.75 & reversible?      │
    │    → Execute immediately                │
    │  - Confidence > 0.75 & irreversible?    │
    │    → Log & escalate                     │
    │  - Confidence < 0.75?                   │
    │    → Queue for HITL review              │
    └─────────────────────────────────────────┘
        ↓
    ┌───────────────────────────────────────────────────────┐
    │  Parallel:                                            │
    │                                                       │
    │  ├─→ HumanReviewQueue (escalated items)             │
    │  │   ├─ Max 100 items                              │
    │  │   ├─ 3-hour timeout                             │
    │  │   └─ Save to /queue/hitl_review.json            │
    │  │                                                   │
    │  └─→ UplinkBundler (actions + responses)           │
    │      ├─ Gzip: 40-70% reduction                    │
    │      ├─ Encrypt: Fernet (FIPS-140-2)             │
    │      ├─ Size limit: 512KB                         │
    │      └─ Save to /output/uplink_bundle_*.json      │
    │                                                    │
    │  Audit Log:                                        │
    │  └─ /logs/autonomous_actions.jsonl                │
    │     {timestamp, node_id, action, confidence, ...} │
    └───────────────────────────────────────────────────────┘
        ↓
    Ready for next contact window transmission
```

---

## Component Interaction Matrix

| Phase | Component | Inputs | Outputs | Storage |
|-------|-----------|--------|---------|---------|
| 1 | TelemetryParser | Raw telemetry JSON | Normalized metrics | In-memory |
| 2 | BaselineCache | Metrics, 30-day stats | Mean, stddev, confidence | config/baselines.json |
| 2 | AnomalyTriager | Metrics, baseline | Z-score, severity | Logs |
| 3 | ResponsePlanner | Anomalies, playbooks | Actions (ranked) | Logs |
| 3 | Decision Logic | Action confidence | Execute/Escalate/Log | Logs |
| 4 | HumanReviewQueue | Escalations | Pending items | queue/hitl_review.json |
| 4 | UplinkBundler | Actions, responses | Encrypted bundle | output/uplink_bundle_*.json |

---

## State Transitions

```
[NOMINAL]
   ↓
   Metric exceeds baseline by 2-sigma
   ↓
[ANOMALY DETECTED]
   ↓
   Severity assigned (WARNING / CRITICAL)
   ↓
[TRIAGED]
   ↓
   Playbook matched, actions proposed
   ↓
[ACTION PLANNED]
   ↓
   ┌──────────────────────────────────┐
   │  Confidence > 0.75?              │
   ├──────────────────────────────────┤
   │  YES (reversible)   → EXECUTING  │
   │  YES (irreversible) → LOGGED     │
   │  NO                 → ESCALATED  │
   └──────────────────────────────────┘
   ↓
[ACTION EXECUTED] or [AWAITING HUMAN DECISION]
   ↓
   Prepare uplink bundle
   ↓
[BUNDLED & ENCRYPTED]
   ↓
   Ready for MCH transmission
   ↓
[TRANSMITTED]
```

---

## Confidence Scoring Flow

```
Anomaly Detected
├─ anomaly_confidence = f(z_score, baseline_age)
│  ├─ z_score > 3.0 → 0.95
│  ├─ 2.5 < z_score ≤ 3.0 → 0.85
│  ├─ 2.0 < z_score ≤ 2.5 → 0.75
│  └─ baseline_age_penalty (↓10% per week old)
│
└─ action_confidence = anomaly_confidence × action.min_confidence
   ├─ 0.75+ → Execute (reversible) or Log (irreversible)
   └─ <0.75 → Escalate to HITL queue
```

---

## Power Budget Enforcement

```
Contact Window Starts
├─ power_budget = node.power_budget_watts
├─ remaining = power_budget × 0.95  (5% safety margin)
│
└─ For each action (in priority order):
   ├─ if (remaining - action.power_cost) > 0:
   │  ├─ Execute action
   │  └─ remaining -= action.power_cost
   └─ else:
      └─ Skip action (insufficient power)

End of contact window → unused budget discarded
```

---

## Encryption Pipeline

```
Uplink Bundle (plaintext JSON)
       ↓
    Gzip compression
    (40-70% reduction)
       ↓
    FIPS-140-2 Fernet encryption
    (symmetric key from OMNICOMPUTE_ENCRYPTION_KEY)
       ↓
    is_encrypted: true
    encryption_algorithm: "Fernet"
    encrypted_payload: base64
       ↓
    Save to output/uplink_bundle_*.json
       ↓
    Ready for SATCOM transmission
```

---

## Graceful Degradation

```
Normal Mode:
  Telemetry → Parse → Detect → Plan → Bundle → Transmit
     100%      95%     90%     85%    95%      100%

Degraded Mode (missing baseline):
  Telemetry → Parse → Use Nominal → Plan → Bundle → Transmit
     100%      95%     (reduced confidence)  95%    100%

Degraded Mode (encryption failure):
  Telemetry → Parse → Detect → Plan → Bundle (unencrypted) → Transmit
     100%      95%     90%     85%    (logged & flagged)    100%

Degraded Mode (queue full):
  Telemetry → Parse → Detect → Plan → Trim old items → Bundle → Transmit
     100%      95%     90%     85%    (keep CRITICAL)  95%     100%

Critical Failure:
  Log error → Alert ground on next contact window
  System restarts on next telemetry batch
```

---

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                  MISSION CONTROL HUB (MCH)                  │
│                  (Always Connected)                         │
│                                                              │
│  ├─ Orchestrator (continuous monitoring)                   │
│  ├─ Baseline cache (centralized, synced every 24h)        │
│  ├─ Playbook repository (source of truth)                 │
│  └─ Human review interface (HITL queue dashboard)         │
└─────────────────────────────────────────────────────────────┘
    ↑                              ↑
    │ Contact Window              │ Contact Window
    │ (8-12 min/orbit)            │ (30+ min, longer)
    │                              │
┌───┴──────────────────────────────┴─────────────────────┐
│                                                         │
│  ┌──────────────┐    ┌──────────────┐                 │
│  │   Sat-01     │    │   Sat-02     │  ...            │
│  │ (onboard AI) │    │ (onboard AI) │                 │
│  │ 2GB RAM      │    │ 2GB RAM      │                 │
│  │ 15W budget   │    │ 15W budget   │                 │
│  └──────────────┘    └──────────────┘                 │
│         ↓                    ↓                         │
│  ┌──────────────┐    ┌──────────────┐                 │
│  │   FGN-Alpha  │    │  FGN-Bravo   │  ...            │
│  │ (forward GN) │    │ (forward GN) │                 │
│  │  8GB RAM     │    │  8GB RAM     │                 │
│  │ 50W budget   │    │ 50W budget   │                 │
│  └──────────────┘    └──────────────┘                 │
│                                                         │
│        Federated Edge Constellation                   │
│        (Each node runs full 4-phase pipeline)         │
│        (No ground contact required for 94 min)        │
└─────────────────────────────────────────────────────────┘
```

---

## Audit Trail Example

```json
{
  "timestamp": "2026-06-20T12:45:30Z",
  "node_id": "Sat-01",
  "metric_name": "battery_soc_percent",
  "metric_value": 14.2,
  "baseline_mean": 65.0,
  "baseline_stddev": 8.0,
  "z_score": -6.35,
  "severity": "CRITICAL",
  "anomaly_confidence": 0.95,
  "playbook_matched": "power_anomaly",
  "proposed_actions": [
    {
      "action_type": "load_shed",
      "min_confidence": 0.6,
      "action_confidence": 0.57,
      "reversible": true
    }
  ],
  "executed_action": "ESCALATED",
  "escalation_reason": "action_confidence (0.57) < threshold (0.75)",
  "queue_item_id": "esc_20260620_124530_sat01_power",
  "timeout_utc": "2026-06-20T15:45:30Z",
  "is_encrypted": true,
  "encryption_algorithm": "Fernet",
  "bundle_id": "uplink_20260620_125000",
  "status": "BUNDLED"
}
```

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
