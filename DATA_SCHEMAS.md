# OmniCompute Data Schemas

## 1. Node Configuration: `/config/nodes.yaml`

Defines the federated node inventory, hardware capabilities, and safe operating ranges.

```yaml
nodes:
  Sat-01:
    node_type: leo_satellite
    contact_window_minutes: 8
    contact_cycle_minutes: 94
    power_budget_watts: 15
    ram_gb: 2
    safe_ranges:
      battery_soc: [20, 100]  # percent
      thermal_temp_celsius: [0, 85]
      rf_signal_strength_dbm: [-120, -30]
    baselines:
      power_draw_watts: { mean: 8.5, stddev: 1.2 }
      battery_soc_percent: { mean: 65.0, stddev: 8.0 }
      thermal_temp_celsius: { mean: 35.0, stddev: 5.0 }
    playbooks: [power_anomaly, thermal_violation, rf_jamming]

  FGN-Alpha:
    node_type: forward_ground_node
    contact_window_minutes: 30  # longer ground contact windows
    power_budget_watts: 50
    ram_gb: 8
    safe_ranges:
      thermal_temp_celsius: [10, 50]
      rf_signal_strength_dbm: [-110, -20]
    baselines:
      compute_load_percent: { mean: 35.0, stddev: 15.0 }
      thermal_temp_celsius: { mean: 28.0, stddev: 8.0 }
    playbooks: [thermal_violation, rf_jamming, compute_overload]

  MCH-Primary:
    node_type: mission_control_hub
    contact_window_minutes: 1440  # always connected
    power_budget_watts: 500
    ram_gb: 64
    role: orchestrator
    playbooks_directory: /playbooks/
    baseline_update_frequency_hours: 24
```

---

## 2. Telemetry Batch: `/data/telemetry_batch_latest.json`

Raw sensor readings from nodes. Produced at end of contact window, consumed by TelemetryParser.

```json
{
  "batch_id": "batch_2026-06-19T20-15-00Z",
  "batch_timestamp_utc": "2026-06-19T20:15:00Z",
  "node_readings": [
    {
      "node_id": "Sat-01",
      "received_at_utc": "2026-06-19T20:10:00Z",
      "metrics": {
        "power_draw_watts": 9.2,
        "battery_soc_percent": 14.2,
        "solar_array_output_watts": 6.5,
        "thermal_sensor_1_celsius": 42.1,
        "rf_signal_strength_dbm": -75.3,
        "uplink_queue_bytes": 125000,
        "downlink_queue_bytes": 45000
      }
    },
    {
      "node_id": "FGN-Alpha",
      "received_at_utc": "2026-06-19T20:10:05Z",
      "metrics": {
        "compute_load_percent": 68.5,
        "thermal_sensor_1_celsius": 51.2,
        "thermal_sensor_2_celsius": 49.8,
        "rf_signal_strength_dbm": -88.1,
        "disk_usage_percent": 82.0
      }
    }
  ]
}
```

### TelemetryParser Output (Normalized)

```python
[
  {
    "node_id": "Sat-01",
    "timestamp": "2026-06-19T20:10:00Z",  # UTC normalized
    "metrics": {
      "power_draw_watts": 9.2,
      "battery_soc_percent": 14.2,
      "solar_array_output_watts": 6.5,
      "thermal_temp_celsius": 42.1,
      "rf_signal_strength_dbm": -75.3,
      "uplink_queue_bytes": 125000,
      "downlink_queue_bytes": 45000
    },
    "received_at": "2026-06-19T20:15:00Z"
  },
  # ... more nodes
]
```

---

## 3. Playbooks: `/playbooks/{anomaly_type}.yaml`

Condition-action rules for autonomous response. One file per anomaly type.

### Example: `/playbooks/power_anomaly.yaml`

```yaml
name: "Power System Anomaly Response"
anomaly_type: power_anomaly
version: "1.0"

# Triggers that activate this playbook
triggers:
  - metric: battery_soc_percent
    condition: "< 15"
    severity: CRITICAL
    description: "Battery critically low"

  - metric: power_draw_watts
    condition: "> 12"
    severity: WARNING
    description: "Power draw exceeds nominal"

# Actions to execute when triggered (in order)
actions:
  - id: "load_shed_1"
    action_type: load_shed
    description: "Shed non-critical subsystems"
    params:
      subsystems: ["thermal_monitor", "rf_backup", "secondary_payload"]
    reversible: true
    reversibility_window_seconds: 600  # can restore for 10 min
    estimated_impact: "+2_hours_runtime"
    min_confidence_for_autonomous: 0.8

  - id: "reduce_beacon"
    action_type: reduce_beacon_interval
    description: "Reduce beacon transmission frequency"
    params:
      old_interval_seconds: 60
      new_interval_seconds: 300
    reversible: true
    estimated_impact: "+30_min_runtime"
    min_confidence_for_autonomous: 0.75

  - id: "thermal_alert"
    action_type: queue_for_hitl_review
    description: "Alert ground if solar degradation detected"
    params:
      condition: "solar_array_degradation_percent > 20"
    reversible: false
    min_confidence_for_autonomous: 0.85

# Conditions that may modify action behavior
modifiers:
  - if: "solar_array_degradation_percent > 20"
    then: "skip_rf_backup_load_shed, rely_on_primary_only"

  - if: "orbit_phase == 'eclipse'"
    then: "more_aggressive_load_shedding"

# Confidence rules
confidence:
  metric_z_score: 1.0  # base confidence from anomaly severity
  baseline_age_days: -0.05  # penalize if baseline is stale
  redundant_indicators: 0.1  # bonus if multiple sensors agree
```

### Example: `/playbooks/thermal_violation.yaml`

```yaml
name: "Thermal Envelope Violation"
anomaly_type: thermal_violation
version: "1.0"

triggers:
  - metric: thermal_temp_celsius
    condition: "> 85"
    severity: CRITICAL

actions:
  - id: "throttle_compute"
    action_type: reduce_compute_frequency
    params:
      target_frequency_mhz: 800  # from 1600 MHz nominal
    reversible: false  # throttle takes ~2 min to recover from
    reversibility_window_seconds: 0  # immediate irreversibility
    estimated_impact: "-40% compute performance"
    min_confidence_for_autonomous: 0.85

  - id: "reduce_payload"
    action_type: pause_payload
    params:
      payload_id: "primary_sensor_suite"
    reversible: true
    estimated_impact: "pause inference until throttle resets"
    min_confidence_for_autonomous: 0.80
```

---

## 4. Autonomous Action Log: `/logs/autonomous_actions.jsonl`

One JSON object per line. Logs every autonomous action executed during blackout.

```jsonl
{"timestamp": "2026-06-19T20:10:15Z", "node_id": "Sat-01", "action": "load_shed_non_critical_subsystems", "params": {"subsystems": ["thermal_monitor", "rf_backup"]}, "rationale": "Battery SOC < 15%, z-score -2.8", "confidence": 0.82, "reversible": true, "result": "success"}
{"timestamp": "2026-06-19T20:10:45Z", "node_id": "Sat-01", "action": "reduce_beacon_interval", "params": {"old_interval_seconds": 60, "new_interval_seconds": 300}, "rationale": "Continued power pressure, beacon overhead 8% of total draw", "confidence": 0.75, "reversible": true, "result": "success"}
{"timestamp": "2026-06-19T20:11:00Z", "node_id": "FGN-Alpha", "action": "queue_for_hitl_review", "action_id": "thermal_throttle_201", "reason": "Confidence 0.68 < 0.75 threshold, thermal_violation_severity=WARNING", "reversible": false, "result": "queued"}
```

---

## 5. Human-in-the-Loop Queue: `/queue/hitl_review.json`

Actions requiring human approval. Updated incrementally throughout orbit.

```json
{
  "queue_id": "Sat-01_orbit_2026-06-19",
  "node_id": "Sat-01",
  "created_at_utc": "2026-06-19T20:05:00Z",
  "next_contact_utc": "2026-06-19T21:50:00Z",
  "items": [
    {
      "action_id": "thermal_throttle_201",
      "recommended_action": "reduce_compute_frequency",
      "action_params": {"target_frequency_mhz": 800},
      "risk_level": "medium",
      "supporting_evidence": [
        "thermal_temp_celsius: 92 (baseline 35, z-score +2.2)",
        "thermal_temp_celsius_sensor_2: 88 (baseline 34, z-score +2.0)",
        "compute_power_draw: 18W (nominal 12W, z-score +2.4)"
      ],
      "confidence": 0.68,
      "reversible": false,
      "queued_at_utc": "2026-06-19T20:10:00Z",
      "timeout_utc": "2026-06-19T23:00:00Z",
      "timeout_action": "execute_with_log_entry_timeout_fallback",
      "notes": "Compute throttle is system-level irreversible; takes ~120s to restore. Ground should respond within 45min if possible."
    },
    {
      "action_id": "rf_freq_switch_202",
      "recommended_action": "switch_to_backup_frequency_band",
      "action_params": {"target_band": "S_band_backup"},
      "risk_level": "low",
      "supporting_evidence": [
        "rf_signal_strength_dbm: -92 (anomalous spike, z-score +3.1)",
        "rf_lock_loss_count: 4 events in last 5min (nominal: 0)"
      ],
      "confidence": 0.90,
      "reversible": true,
      "queued_at_utc": "2026-06-19T20:09:30Z",
      "timeout_utc": "2026-06-19T22:30:00Z",
      "timeout_action": "execute_autonomously_if_timeout",
      "notes": "RF jamming detected (likely spoofing signal). Backup band is safe fallback; recommend ground confirm jam source."
    }
  ]
}
```

---

## 6. Uplink Bundle: `/output/uplink_bundle_{timestamp}.json`

Compressed, encrypted bundle for ground. Sent at next contact window.

```json
{
  "bundle_id": "uplink_2026-06-19T21-50-00Z",
  "node_id": "Sat-01",
  "timestamp_utc": "2026-06-19T21:50:00Z",
  "size_bytes": 48192,
  "priority_tier": 1,
  
  "anomalies_summary": {
    "total_anomalies": 3,
    "by_severity": {
      "CRITICAL": 1,
      "WARNING": 2,
      "NOMINAL": 0
    },
    "anomalies": [
      {
        "metric": "battery_soc_percent",
        "value": 14.2,
        "baseline_mean": 65.0,
        "z_score": -2.8,
        "severity": "CRITICAL"
      },
      {
        "metric": "thermal_temp_celsius",
        "value": 92.0,
        "baseline_mean": 35.0,
        "z_score": +2.2,
        "severity": "WARNING"
      },
      {
        "metric": "rf_signal_strength_dbm",
        "value": -92,
        "baseline_mean": -75,
        "z_score": +3.1,
        "severity": "WARNING"
      }
    ]
  },

  "actions_taken": [
    {
      "action_id": "load_shed_1",
      "action": "load_shed_non_critical_subsystems",
      "timestamp": "2026-06-19T20:10:15Z",
      "result": "success",
      "reversible": true
    },
    {
      "action_id": "reduce_beacon",
      "action": "reduce_beacon_interval",
      "timestamp": "2026-06-19T20:10:45Z",
      "result": "success",
      "reversible": true
    }
  ],

  "ground_recommendations": [
    {
      "recommendation_id": "solar_angle_adjust",
      "action": "increase_solar_panel_angle",
      "rationale": "Solar array output degraded 25%; angle adjustment may recover 5-8% efficiency",
      "estimated_impact": "+1.5_hours_runtime_per_orbit",
      "confidence": 0.82,
      "reversible": true
    }
  ],

  "hitl_queue": [
    {
      "action_id": "thermal_throttle_201",
      "recommended_action": "reduce_compute_frequency",
      "risk_level": "medium",
      "evidence": ["thermal_temp_celsius: 92 (z-score +2.2)", "compute_power_draw: 18W (z-score +2.4)"],
      "confidence": 0.68,
      "reversible": false,
      "queued_at_utc": "2026-06-19T20:10:00Z",
      "timeout_utc": "2026-06-19T23:00:00Z"
    }
  ]
}
```

---

## 7. Baseline Cache: `/config/baselines.json`

Rolling 30-day statistics updated after each ground uplink.

```json
{
  "last_updated_utc": "2026-06-19T21:50:00Z",
  "nodes": {
    "Sat-01": {
      "power_draw_watts": { "mean": 8.5, "stddev": 1.2, "days_samples": 28 },
      "battery_soc_percent": { "mean": 65.0, "stddev": 8.0, "days_samples": 30 },
      "solar_array_output_watts": { "mean": 10.2, "stddev": 2.1, "days_samples": 25 },
      "thermal_temp_celsius": { "mean": 35.0, "stddev": 5.0, "days_samples": 30 },
      "rf_signal_strength_dbm": { "mean": -75.0, "stddev": 8.5, "days_samples": 30 }
    },
    "FGN-Alpha": {
      "compute_load_percent": { "mean": 35.0, "stddev": 15.0, "days_samples": 30 },
      "thermal_temp_celsius": { "mean": 28.0, "stddev": 8.0, "days_samples": 30 }
    }
  }
}
```

---

## Summary

| File | Purpose | Produced By | Consumed By |
|------|---------|-------------|-------------|
| `/config/nodes.yaml` | Node inventory & safe ranges | Ground | AnomalyTriager, ResponsePlanner |
| `/config/baselines.json` | 30-day baseline stats | Ground (uplink) | AnomalyTriager |
| `/data/telemetry_batch_latest.json` | Raw sensor readings | Node (periodic) | TelemetryParser |
| `/playbooks/*.yaml` | Condition-action rules | Ground (updates) | ResponsePlanner |
| `/logs/autonomous_actions.jsonl` | Action audit log | ResponsePlanner | UplinkBundler (summary) |
| `/queue/hitl_review.json` | HITL escalations | ResponsePlanner | UplinkBundler, Ground |
| `/output/uplink_bundle_{timestamp}.json` | Compressed uplink packet | UplinkBundler | Ground (next contact) |

