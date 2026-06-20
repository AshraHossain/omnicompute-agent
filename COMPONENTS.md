# OmniCompute Components

**Production Ready** — 8 components, 155 tests, 97% coverage, all phases complete

## Quick Navigation

📖 **Documentation**:
- [README.md](README.md) — Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design and philosophy
- [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — Data model specifications
- [TESTING.md](TESTING.md) — Test suite details
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment guide
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development setup
- [SECURITY.md](SECURITY.md) — Security and compliance
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines

## Status Summary

| Component | Phase | Tests | Coverage | Status |
|-----------|-------|-------|----------|--------|
| TelemetryParser | 1 | 24 | 88% | ✅ Complete |
| BaselineCache | 1 | 14 | 90% | ✅ Complete |
| AnomalyTriager | 1 | 25 | 100% | ✅ Complete |
| ResponsePlanner | 2 | 17 | 90% | ✅ Complete |
| HumanReviewQueue | 2 | 22 | 90% | ✅ Complete |
| UplinkBundler | 3 | 19 | 87% | ✅ Complete |
| Orchestrator | 3 | 20 | 92% | ✅ Complete |
| Integration | 4 | 18 | 99% | ✅ Complete |

---

## 1. TelemetryParser

**Responsibility**: Ingest heterogeneous sensor data from distributed nodes, normalize to canonical schema, align timestamps, convert units.

**Inputs**:
- `/data/telemetry_batch_latest.json` — JSON array of raw sensor readings

**Outputs**:
- Normalized telemetry dict with keys: `node_id`, `timestamp`, `metrics` (dict), `received_at`

**Key Operations**:
- Parse incoming JSON batch
- Validate required fields (node_id, timestamp)
- Unit conversion (Celsius → Kelvin, mAh → %), timestamp UTC normalization
- Skip malformed records, log errors
- Return parsed & validated list

**Error Handling**:
- Malformed JSON → log and skip record
- Missing required fields → log warning, mark record as incomplete
- Invalid metrics → coerce to float, use 0.0 as fallback for missing numeric values

---

## 2. AnomalyTriager

**Responsibility**: Detect metric deviations > 2-sigma from 30-day rolling baseline. Assign severity levels and confidence scores.

**Inputs**:
- Normalized telemetry from TelemetryParser
- Baseline statistics (loaded from local cache or ground)

**Outputs**:
- List of anomalies with:
  - `node_id`, `metric_name`, `current_value`, `baseline_mean`, `baseline_stddev`
  - `z_score`, `severity` (CRITICAL / WARNING / NOMINAL)
  - `timestamp`, `confidence` (0.0–1.0)

**Severity Rules**:
- `CRITICAL`: |z-score| > 3.0 OR metric outside safe operating range
- `WARNING`: 2.0 < |z-score| ≤ 3.0
- `NOMINAL`: |z-score| ≤ 2.0

**Baseline Calculation**:
- Rolling 30-day window of historical metrics per node + metric
- Stored in `/config/baselines.json` (mean, stddev per metric)
- Updated after each uplink from ground

**Key Operations**:
- For each normalized metric, compute z-score: `(value - mean) / stddev`
- Lookup safe operating ranges (from node spec)
- Assign severity and confidence based on z-score magnitude
- Flag metrics with incomplete baseline (< 7 days history) as AMBIGUOUS confidence

---

## 3. ResponsePlanner

**Responsibility**: Load anomaly-specific playbooks, evaluate conditions, recommend or execute responses.

**Inputs**:
- Anomaly list from AnomalyTriager
- Playbook definitions from `/playbooks/` directory

**Outputs**:
- Response actions with:
  - `node_id`, `action_type`, `action_params`
  - `rationale`, `reversible` (bool), `estimated_impact`, `confidence` (0.0–1.0)

**Playbook Structure**:
```yaml
# /playbooks/power_anomaly.yaml
anomaly_type: power_anomaly
triggers:
  - metric: battery_soc
    condition: "< 15"
    severity: CRITICAL
actions:
  - action: load_shed_non_critical_subsystems
    params:
      subsystems: [thermal_monitor, rf_backup, secondary_payload]
    reversible: true
    estimated_impact: +2_hours_runtime
  - action: reduce_beacon_interval
    params:
      old_interval_sec: 60
      new_interval_sec: 300
    reversible: true
    estimated_impact: +30_min_runtime
conditions:
  - if: "solar_array_degradation > 20%"
    then: "skip rf_backup, rely on primary only"
```

**Key Operations**:
- Match anomaly type to playbook file
- Evaluate playbook trigger conditions
- If triggered, generate response actions
- Mark actions as `reversible: true` if state can be restored
- Assign confidence based on condition match certainty

**Fallback**: If no playbook exists for anomaly, generate generic recommendation (e.g., "alert ground, hold for HITL review")

---

## 4. UplinkBundler

**Responsibility**: Compress telemetry, action logs, and recommendations into a prioritized, encrypted uplink bundle capped at 512KB.

**Inputs**:
- Anomaly list (from AnomalyTriager)
- Response actions taken (from ResponsePlanner + autonomous execution log)
- Queue of pending actions (from HumanReviewQueue)

**Outputs**:
- `/output/uplink_bundle_{timestamp}.json` — encrypted, < 512KB

**Bundle Structure**:
```json
{
  "timestamp": "2026-06-19T20:15:00Z",
  "node_id": "Sat-01",
  "anomalies": [
    {
      "metric": "battery_soc",
      "value": 14.2,
      "baseline": 65.0,
      "z_score": -2.8,
      "severity": "CRITICAL"
    }
  ],
  "actions_taken": [
    {
      "action": "load_shed_non_critical_subsystems",
      "timestamp": "2026-06-19T20:10:00Z",
      "result": "success",
      "reversible": true
    }
  ],
  "recommendations": [
    {
      "action": "increase_solar_panel_angle",
      "rationale": "maximize energy harvest",
      "confidence": 0.82,
      "reversible": true
    }
  ],
  "hitl_queue": [
    {
      "node_id": "Sat-01",
      "action": "emergency_shutdown_payload_suite",
      "risk_level": "high",
      "evidence": ["thermal_violation_5x_baseline"],
      "timeout_utc": "2026-06-19T22:00:00Z"
    }
  ]
}
```

**Compression Strategy**:
- Drop verbose metadata; keep only essentials
- Summarize anomaly data (count by severity, not individual records if > 10)
- Exclude actions with timestamp > 6 hours ago
- Prioritize CRITICAL / HITL items first; trim bottom if over budget

**Encryption**:
- FIPS-140-2 AES-256-GCM
- Key derived from node identity + shared secret

**Key Operations**:
1. Collect all anomalies, actions, recommendations, HITL queue items
2. Serialize to JSON
3. Compress (gzip)
4. Encrypt (AES-256-GCM)
5. Check size; if > 512KB, trim low-priority items
6. Write to `/output/uplink_bundle_{timestamp}.json`
7. Return bundle size and priority tier (1=critical, 2=standard, 3=optional)

---

## 5. HumanReviewQueue

**Responsibility**: Hold and escalate low-confidence or irreversible actions for ground human review.

**Inputs**:
- Response actions from ResponsePlanner where:
  - `reversible: false` OR
  - `confidence < 0.75`

**Outputs**:
- `/queue/hitl_review.json` — queue of pending decisions

**Queue Item Format**:
```json
{
  "node_id": "FGN-Alpha",
  "action_id": "thermal_throttle_201",
  "recommended_action": "reduce_compute_clock_speed",
  "risk_level": "medium",
  "supporting_evidence": [
    "thermal_sensor_1: 92°C (baseline 55°C, +67% anomaly)",
    "thermal_sensor_2: 88°C (baseline 54°C, +63% anomaly)",
    "compute_power_draw: 18W (normal max 12W)"
  ],
  "confidence": 0.68,
  "reversible": false,
  "queued_at_utc": "2026-06-19T20:10:00Z",
  "timeout_utc": "2026-06-19T22:00:00Z",
  "notes": "Throttle is irreversible for ~2 min; if ground does not respond by timeout, autonomous execution fallback."
}
```

**Key Operations**:
1. Filter response actions for `reversible: false` or `confidence < 0.75`
2. Append to `/queue/hitl_review.json` with:
   - `queued_at_utc`: when the action was proposed
   - `timeout_utc`: deadline for ground to respond (typically +2 orbits = 3 hours)
3. On uplink, include HITL queue in the bundle (highest priority)
4. Ground acknowledges HITL decisions and sends back ground response
5. On receipt, update queue item status: `resolved` or `timeout_fallback`
6. If timeout expires before ground contact, execute fallback action

**Fallback Behavior**:
- If `confidence < 0.75` and timeout expires: escalate to CRITICAL severity for next orbit
- If `reversible: false` and timeout expires: execute action with explicit log entry "timeout_fallback_execution"
- Never execute `reversible: false` actions without human override OR timeout expiry

---

## Interaction Diagram

```
TelemetryParser
    │
    ├─► Normalize JSON, validate schema
    │
    ▼
AnomalyTriager
    │
    ├─► Compute z-scores
    ├─► Assign severity
    │
    ▼
ResponsePlanner
    │
    ├─► Load playbooks
    ├─► Evaluate conditions
    │
    ├─► if reversible && confidence >= 0.75:
    │       Execute autonomously
    │       Log action
    │
    ├─► if reversible: false OR confidence < 0.75:
    │       HumanReviewQueue.enqueue(action)
    │
    ▼
UplinkBundler
    │
    ├─► Collect anomalies, actions, HITL queue
    ├─► Compress, encrypt, cap at 512KB
    │
    ▼
/output/uplink_bundle_{timestamp}.json → Next Contact Window
```

