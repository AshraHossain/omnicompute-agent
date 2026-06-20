# Glossary

**OmniCompute Technical Terminology & Acronyms**

---

## Core Concepts

### **Anomaly**
A metric value that deviates significantly from its 30-day baseline. Detected using Z-score analysis.
- **See**: [Z-score](#z-score), [Baseline](#baseline), [Severity](#severity)
- **Related files**: ARCHITECTURE.md, COMPONENTS.md

### **Baseline**
30-day rolling statistical profile of a metric. Stores mean and standard deviation for Z-score calculation.
- **Format**: `mean: 65.0, stddev: 8.0, updated_at: "2026-06-20T12:00:00Z"`
- **Location**: `config/baselines.json`
- **Age penalty**: 10% confidence loss per week old
- **See**: [Z-score](#z-score), [Baseline Cache](#baseline-cache)

### **Confidence Score**
Probability (0.0-1.0) that a decision is correct. Calculated as:
```
action_confidence = anomaly_confidence × action.min_confidence
```
- **Escalation threshold**: 0.75
- **Below 0.75**: Route to HITL queue
- **Above 0.75**: Execute autonomously (if reversible)
- **See**: [HITL](#human-in-the-loop-hitl), [Escalation](#escalation)

### **Contact Window**
Period of satellite-ground connectivity, typically 5-12 minutes per orbit (~94 minute cycle for LEO).
- **Used for**: Uplink bundles, downlink telemetry, baseline sync
- **Limitation**: 512KB max bundle size (gzip + encryption)
- **See**: [LEO](#leo), [Uplink Bundle](#uplink-bundle)

### **Graceful Degradation**
System continuing to operate at reduced capability when components fail or data is missing.
- **Examples**:
  - Missing baseline → use nominal values
  - Missing playbook → escalate to HITL
  - Encryption failure → log and continue
  - Queue full → trim low-risk items
- **See**: [Nominal Values](#nominal-values), [Queue Management](#queue-management)

### **Playbook**
YAML file defining responses to specific anomaly types. Contains triggers, actions, modifiers, and test cases.
- **Format**: `config/playbooks/<name>.yaml`
- **Example**: `example_power_anomaly.yaml`
- **Fields**: `anomaly_type`, `triggers`, `actions`, `modifiers`, `success_criteria`
- **See**: [YAML](#yaml), [Trigger](#trigger), [Action](#action)

### **Severity**
Classification of anomaly importance:
- **CRITICAL**: Z-score > 3.0 OR metric exceeds safe range (hard limit)
- **WARNING**: 2.0 < Z-score ≤ 3.0
- **NOMINAL**: Z-score < 2.0
- **See**: [Z-score](#z-score), [Safe Range](#safe-range)

---

## 4-Phase Pipeline

### **Phase 1: Telemetry Ingestion**
Parse and normalize raw sensor data from distributed nodes.
- **Component**: TelemetryParser
- **Input**: JSON telemetry from satellites/ground nodes
- **Output**: Normalized metrics
- **See**: COMPONENTS.md, ARCHITECTURE.md

### **Phase 2: Anomaly Detection**
Compare metrics against baselines; assign severity and confidence.
- **Components**: BaselineCache, AnomalyTriager
- **Input**: Normalized metrics
- **Output**: Anomalies with Z-score, severity, confidence
- **See**: COMPONENTS.md, ARCHITECTURE.md

### **Phase 3: Decision Planning**
Match anomalies to playbooks; generate candidate actions with confidence scores.
- **Component**: ResponsePlanner
- **Input**: Anomalies, playbooks
- **Output**: Ranked actions with confidence scores
- **Decision**: Execute / Escalate / Log
- **See**: COMPONENTS.md, ARCHITECTURE.md

### **Phase 4: Bundle & Queue**
Encrypt bundles for uplink; queue irreversible/low-confidence items for human review.
- **Components**: HumanReviewQueue, UplinkBundler
- **Input**: Executed actions, escalations
- **Output**: Encrypted bundle (<512KB), HITL queue
- **See**: COMPONENTS.md, ARCHITECTURE.md

---

## Components

### **Baseline Cache**
In-memory cache of 30-day rolling statistics for anomaly detection.
- **Storage**: `config/baselines.json`
- **Metrics per node**: battery_soc_percent, thermal_temp_celsius, rf_signal_strength_dbm, ...
- **Updated**: Every 24 hours from MCH-Primary
- **Confidence decay**: -10% per week old
- **See**: [Baseline](#baseline)

### **Telemetry Parser**
Validates, normalizes, and extracts metrics from raw telemetry.
- **Input format**: JSON
- **Handles**: Missing fields, invalid types, out-of-order data
- **Output**: Normalized metrics ready for anomaly detection
- **See**: [Graceful Degradation](#graceful-degradation)

### **Anomaly Triager**
Compares metrics to baselines; assigns severity and confidence using Z-score.
- **Formula**: `z = (value - mean) / stddev`
- **Severity logic**: Combines Z-score + safe range violations
- **Confidence**: Baseline age penalty applied
- **See**: [Z-score](#z-score), [Severity](#severity), [Baseline Age Penalty](#baseline-age-penalty)

### **Response Planner**
Matches anomalies to playbooks; generates actions with confidence scores.
- **Inputs**: Anomalies, playbooks, node config
- **Outputs**: Ranked actions (by confidence × reversibility)
- **Constraints**: Power budget, action reversibility
- **Modifiers**: Eclipse, solar degradation
- **See**: [Playbook](#playbook), [Confidence Score](#confidence-score), [Modifier](#modifier)

### **Human-in-the-Loop Queue (HITL)**
Holds escalations awaiting human decision.
- **Capacity**: Max 100 items
- **Trimming**: Oldest low-risk items removed when full
- **Timeout**: 3 hours for irreversible actions
- **Fallback**: Execute (conf>0.75) or alert ground (conf<0.75)
- **Storage**: `queue/hitl_review.json`
- **See**: [Escalation](#escalation), [Timeout](#timeout)

### **Uplink Bundler**
Compresses and encrypts data for transmission to Mission Control Hub.
- **Compression**: Gzip (40-70% typical)
- **Encryption**: Fernet (FIPS-140-2 compliant)
- **Size limit**: 512KB (LEO contact window constraint)
- **Priority**: CRITICAL items first
- **Output**: `output/uplink_bundle_{timestamp}.json`
- **See**: [Fernet](#fernet), [Gzip](#gzip)

### **Orchestrator**
Coordinates all 4 phases; entry point for telemetry processing.
- **Method**: `process_telemetry(batch)`
- **Outputs**: Uplink bundle, HITL queue, audit log
- **See**: COMPONENTS.md

---

## Key Acronyms

### **CRITICAL**
Highest severity level for anomalies. Requires immediate action or escalation.
- **Trigger**: Z-score > 3.0 OR metric exceeds safe range
- **Action**: Execute or escalate (never ignore)

### **FIPS-140-2**
Federal Information Processing Standards Level 1. Security certification for encryption algorithms.
- **OmniCompute uses**: Fernet (approved cryptographic library)
- **For**: Classified data protection, ITAR compliance
- **See**: [Fernet](#fernet), [ITAR](#itar)

### **Fernet**
Symmetric encryption algorithm from the `cryptography` library. FIPS-140-2 Level 1 compliant.
- **Key**: 256-bit random (base64 encoded)
- **Used for**: Uplink bundle encryption
- **Environment variable**: `OMNICOMPUTE_ENCRYPTION_KEY`
- **Rotation**: Monthly (recommended)
- **See**: [Encryption](#encryption), [FIPS-140-2](#fips-140-2)

### **Gzip**
Lossless compression algorithm. Achieves 40-70% reduction on telemetry JSON.
- **Used for**: Uplink bundle compression (before encryption)
- **Ratio**: Depends on data structure and repetition
- **See**: [Compression](#compression)

### **HITL**
Human-in-the-Loop. When autonomous system escalates decision to human operator.
- **Queue**: Max 100 items
- **Timeout**: 3 hours
- **Trigger**: Confidence < 0.75 OR irreversible action
- **See**: [Human-in-the-Loop Queue (HITL)](#human-in-the-loop-queue-hitl), [Escalation](#escalation)

### **ITAR**
International Traffic in Arms Regulations. U.S. export control for defense-related technology.
- **OmniCompute support**: `classified: true` flag on nodes
- **Requirement**: FIPS-140-2 encryption for classified data
- **Routing**: Classified bundles isolated from unclassified channels
- **See**: [FIPS-140-2](#fips-140-2), [Classified Data](#classified-data)

### **JSON**
JavaScript Object Notation. Standard data format for telemetry, configs, and logs.
- **Files**: nodes.yaml, baselines.json, playbooks/*.yaml, uplink_bundle_*.json
- **Logs**: autonomous_actions.jsonl (JSON Lines format)
- **See**: [YAML](#yaml)

### **LEO**
Low Earth Orbit. Satellite altitude 200-2000 km. Defines contact windows and uplink constraints.
- **Contact cycle**: ~90-120 minutes
- **Contact window**: ~5-12 minutes
- **Implications**: Intermittent connectivity, offline processing required
- **See**: [Contact Window](#contact-window)

### **MCH**
Mission Control Hub. Always-connected orchestrator node for baseline sync and HITL review.
- **Location**: Ground station
- **Connectivity**: 24/7 reliable network
- **Role**: Baseline updates, playbook distribution, escalation review
- **ID**: MCH-Primary
- **See**: [Baseline](#baseline), [Playbook](#playbook), [HITL](#hitl)

### **PII**
Personally Identifiable Information. Must never be logged or transmitted in bundles.
- **Examples**: Email addresses, names, phone numbers
- **Policy**: OmniCompute strips all PII from logs
- **Audit**: Monthly check for PII leakage
- **See**: [Security](#security)

### **Reversible Action**
Action that can be undone if it causes problems (e.g., reduce power, switch frequency).
- **Execution**: Can execute autonomously if confidence > 0.75
- **Opposite**: Irreversible actions (e.g., send alert) → must escalate if confidence < 0.75
- **See**: [Action](#action), [Confidence Score](#confidence-score)

### **YAML**
YAML Ain't Markup Language. Configuration file format (human-readable).
- **Files**: `nodes.yaml`, `config/playbooks/*.yaml`
- **Syntax**: Indentation-based (2 spaces per level, no tabs)
- **See**: [JSON](#json)

### **Z-score**
Statistical measure of deviation from mean. Formula: `(value - mean) / stddev`
- **Interpretation**: Number of standard deviations from mean
- **Thresholds**:
  - Z > 3.0: CRITICAL (1 in 370 chance of normal variation)
  - 2.0 < Z ≤ 3.0: WARNING (1 in 22 chance)
  - Z < 2.0: NOMINAL
- **Calculation**: Performed by AnomalyTriager
- **See**: [Baseline](#baseline), [Severity](#severity)

---

## Technical Terms

### **Action**
Response to an anomaly. Defined in playbooks.
- **Fields**: `action_type`, `description`, `params`, `reversible`, `min_confidence`, `power_cost_watts`
- **Execution**: Based on confidence score
- **Example**: Load shedding, alert ground, maximize solar
- **See**: [Playbook](#playbook), [Reversible Action](#reversible-action)

### **Anomaly Confidence**
Probability that a detected anomaly is real (not noise). Influenced by:
- Z-score magnitude
- Baseline age (age penalty: -10% per week)
- Historical false positive rate
- **See**: [Confidence Score](#confidence-score), [Baseline Age Penalty](#baseline-age-penalty)

### **Baseline Age Penalty**
Confidence reduction for stale baselines:
- Fresh (<7 days): No penalty
- 7-14 days old: -10% penalty
- 14-30 days old: -20% penalty
- 30+ days old: -30% penalty
- **See**: [Baseline](#baseline), [Baseline Cache](#baseline-cache)

### **Bundle**
Encrypted, compressed uplink package containing actions and responses.
- **Format**: JSON (gzipped + Fernet encrypted)
- **Size limit**: 512KB
- **Contents**: Anomaly reports, actions taken, responses needed
- **Transmission**: During contact window
- **See**: [Uplink Bundle](#uplink-bundle), [Gzip](#gzip), [Fernet](#fernet)

### **Classified Data**
Information protected by ITAR or other regulations.
- **Flag**: `classified: true` in node config
- **Encryption**: FIPS-140-2 required
- **Routing**: Isolated from unclassified channels
- **Audit**: Monthly compliance check
- **See**: [ITAR](#itar), [FIPS-140-2](#fips-140-2)

### **Compression**
Data size reduction (gzip). Typical 40-70% on JSON telemetry.
- **Tool**: gzip (standard library)
- **Applied**: Before encryption in uplink bundle
- **Ratio**: Varies by data structure and repetition
- **See**: [Gzip](#gzip), [Bundle](#bundle)

### **Encryption**
Data scrambling for security. OmniCompute uses Fernet.
- **Algorithm**: Fernet (symmetric, FIPS-140-2)
- **Key**: 256-bit random (base64 encoded)
- **Applied**: After gzip compression
- **Rotation**: Monthly
- **See**: [Fernet](#fernet), [FIPS-140-2](#fips-140-2)

### **Escalation**
Routing uncertain decision to human for review.
- **Trigger**: Confidence < 0.75 OR irreversible action
- **Queue**: HITL (max 100 items)
- **Timeout**: 3 hours
- **Fallback**: Execute (conf>0.75) or alert (conf<0.75)
- **See**: [HITL](#hitl), [Confidence Score](#confidence-score)

### **Modifier**
Context-based adjustment to action behavior.
- **Examples**: Eclipse (no solar), solar degradation (panels failing)
- **Effect**: Multiplier on action parameters (e.g., aggressive_load_shed: 1.5x)
- **Implementation**: `modifiers` section of playbook
- **See**: [Playbook](#playbook)

### **Nominal Values**
Default baseline statistics used when real baseline unavailable.
- **Cold start**: First orbit has no baseline
- **Usage**: Reduced detection precision until baseline accumulates
- **Duration**: 30 days to convergence
- **See**: [Baseline](#baseline), [Graceful Degradation](#graceful-degradation)

### **Power Budget**
Maximum energy available for actions per contact window.
- **Allocated**: Per node (15W satellites, 50W ground nodes)
- **Enforcement**: 5% safety margin (can use 95% of budget)
- **Unused**: Discarded at end of contact window
- **See**: [Reversible Action](#reversible-action), [Contact Window](#contact-window)

### **Safe Range**
Hard limit on metric values. Violation → CRITICAL anomaly.
- **Example**: battery_soc_percent < 10% or > 100%
- **Behavior**: Bypasses Z-score, immediate CRITICAL severity
- **Configured**: Per node in `nodes.yaml`
- **See**: [Severity](#severity), [Playbook](#playbook)

### **Timeout**
Time limit for escalated decision. Default 3 hours.
- **Trigger**: If not resolved within timeout:
  - Confidence > 0.75: Execute autonomously
  - Confidence < 0.75: Alert ground (stay escalated)
- **Purpose**: Prevent satellite getting stuck waiting for ground contact
- **See**: [HITL](#hitl), [Escalation](#escalation)

### **Trigger**
Condition that activates a playbook.
- **Fields**: `metric`, `severity`, `min_z_score`, `max_z_score`
- **Example**: metric: battery_soc_percent, severity: CRITICAL, min_z_score: 3.0
- **Logic**: All conditions must match
- **See**: [Playbook](#playbook), [Z-score](#z-score)

---

## File Locations

| File | Purpose | Location |
|------|---------|----------|
| Node config | Inventory & safe ranges | `config/nodes.yaml` |
| Baselines | 30-day statistics | `config/baselines.json` |
| Playbooks | Response definitions | `config/playbooks/*.yaml` |
| Encryption key | Uplink security | `$OMNICOMPUTE_ENCRYPTION_KEY` |
| Uplink bundles | Encrypted output | `output/uplink_bundle_*.json` |
| Audit logs | Decision history | `logs/autonomous_actions.jsonl` |
| HITL queue | Escalations | `queue/hitl_review.json` |

---

## Related Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — System design & data flows
- **[COMPONENTS.md](COMPONENTS.md)** — Component contracts & interfaces
- **[FAQ.md](FAQ.md)** — Common questions & answers
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** — Issues & solutions
- **[OPERATIONS.md](OPERATIONS.md)** — Daily operational procedures
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** — Pre-launch verification

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
