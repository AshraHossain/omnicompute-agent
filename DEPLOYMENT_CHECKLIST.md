# Deployment Checklist

**OmniCompute v1.0.0 — Pre-Flight Verification & Go/No-Go Decision**

Complete this checklist **before** deploying to production satellites or ground nodes.

---

## Pre-Deployment Phase (1-2 weeks before)

### Infrastructure & Hardware

- [ ] **Satellite Specifications Verified**
  - [ ] Python 3.10+ installed and tested
  - [ ] 2GB RAM available (minimum)
  - [ ] 15W power budget confirmed
  - [ ] Contact window cycle: 90-120 minutes (typical LEO)
  - [ ] Uplink/downlink connectivity tested
  - [ ] Ephemeris current (within 7 days)

- [ ] **Ground Node Specifications Verified**
  - [ ] Python 3.10+ installed and tested
  - [ ] 8GB RAM available (minimum)
  - [ ] 50W+ power budget confirmed
  - [ ] Network connectivity stable
  - [ ] NTP synchronization operational

- [ ] **Mission Control Hub Ready**
  - [ ] 64GB RAM available
  - [ ] Full network connectivity confirmed
  - [ ] 24/7 availability guaranteed
  - [ ] Redundant power supply installed
  - [ ] Backup uplink path available

### Software Prerequisites

- [ ] **Dependencies Installed**
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

- [ ] **All Tests Pass**
  ```bash
  pytest src/omnicompute/tests/ -v
  # Expected: 155/155 passing
  ```

- [ ] **Type Checking Clean**
  ```bash
  mypy src/omnicompute --strict
  # Expected: 0 errors
  ```

- [ ] **No Lint Violations**
  ```bash
  flake8 src/omnicompute
  # Expected: 0 violations
  ```

### Documentation Review

- [ ] Deployment guide reviewed ([DEPLOYMENT.md](DEPLOYMENT.md))
- [ ] Architecture understood ([ARCHITECTURE.md](ARCHITECTURE.md))
- [ ] All 4 phases understood ([README.md](README.md))
- [ ] Team trained on operations ([OPERATIONS.md](OPERATIONS.md))

---

## Configuration Phase (1 week before)

### Node Inventory Configuration

- [ ] **nodes.yaml Created & Validated**
  ```bash
  cp config/nodes.yaml.example config/nodes.yaml
  python -c "import yaml; yaml.safe_load(open('config/nodes.yaml'))"
  # Expected: No YAML errors
  ```

- [ ] **All Nodes Listed**
  - [ ] Sat-01, Sat-02, ... (all satellites)
  - [ ] FGN-Alpha, FGN-Bravo, ... (all ground nodes)
  - [ ] MCH-Primary (mission control)

- [ ] **Safe Ranges Configured**
  - [ ] battery_soc_percent: [10, 100]
  - [ ] thermal_temp_celsius: [-50, 85]
  - [ ] rf_signal_strength_dbm: [-120, -30]
  - [ ] Additional metrics for your hw: ✓

- [ ] **Power Budgets Realistic**
  - [ ] Satellites: 15W (verified from specs)
  - [ ] Ground nodes: 50W+ (verified from specs)
  - [ ] Margin for contingencies: 5%

- [ ] **Contact Windows Accurate**
  - [ ] Satellite cycle: 90-120 min
  - [ ] Satellite window: 5-12 min
  - [ ] Ground nodes: 30+ min
  - [ ] MCH: 1440 min (always on)

### Playbook Configuration

- [ ] **Playbooks Created for All Anomaly Types**
  ```bash
  ls config/playbooks/*.yaml
  # Expected: power_anomaly, thermal_violation, rf_jamming, etc.
  ```

- [ ] **Each Playbook Complete**
  - [ ] anomaly_type defined
  - [ ] triggers configured (metric, severity, z_score)
  - [ ] actions in priority order
  - [ ] modifiers for eclipse/degradation
  - [ ] success_criteria defined
  - [ ] fallback_action set

- [ ] **Playbooks Assigned to Nodes**
  - [ ] Each satellite has 3+ playbooks
  - [ ] Each ground node has relevant playbooks
  - [ ] No nodes without playbooks

- [ ] **Playbook Test Cases Pass**
  ```bash
  jq '.test_cases' config/playbooks/*.yaml
  # All test cases should succeed
  ```

### Baseline Configuration

- [ ] **Baseline File Created**
  ```bash
  # Either:
  # 1. Initialize from 30 days of historical telemetry
  python scripts/compute_baseline.py <telemetry_archive>
  # 2. Use nominal values for cold start
  cp config/baselines.nominal.json config/baselines.json
  ```

- [ ] **Baseline Completeness Check**
  ```bash
  jq '[.[] | {node: .id, metrics: (.[].keys | length)}]' config/baselines.json
  # Expected: All nodes have baseline for all metrics
  ```

- [ ] **Baseline Quality Verified**
  ```bash
  jq '.[] | .battery_soc_percent | {mean, stddev}' config/baselines.json
  # Expected: stddev > 1.0 (not too tight)
  ```

### Encryption Setup

- [ ] **Encryption Key Generated**
  ```bash
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```

- [ ] **Key Stored Securely**
  - [ ] NOT in source code ✓
  - [ ] Stored in environment variable: OMNICOMPUTE_ENCRYPTION_KEY
  - [ ] OR stored in secret manager
  - [ ] Backed up in secure vault
  - [ ] Rotation schedule defined (monthly minimum)

- [ ] **FIPS-140-2 Compliance Verified**
  ```bash
  python -c "from cryptography.fernet import Fernet; Fernet(b'$OMNICOMPUTE_ENCRYPTION_KEY'); print('✓ Valid')"
  ```

---

## Security Phase (1 week before)

### Code Security Audit

- [ ] **No Hardcoded Secrets**
  ```bash
  grep -r "password\|token\|key\|secret" src/ --include="*.py"
  # Expected: 0 matches (except in config examples)
  ```

- [ ] **No PII in Logs**
  ```bash
  grep -r "@\|email\|phone" src/ --include="*.py"
  # Expected: 0 matches
  ```

- [ ] **Input Validation Comprehensive**
  - [ ] TelemetryParser validates all inputs
  - [ ] Playbook actions validate parameters
  - [ ] Queue items validated before processing

- [ ] **Error Messages Don't Leak Data**
  - [ ] Errors redacted in logs
  - [ ] Stack traces not in uplink bundles
  - [ ] Sensitive data masked

### Data Protection

- [ ] **ITAR Classification Correct**
  - [ ] classified=true for nodes on restricted networks
  - [ ] All classified bundles encrypted
  - [ ] No classified data in unencrypted logs

- [ ] **Data Retention Policy Defined**
  - [ ] Logs archived after 90 days
  - [ ] Queue items purged after resolution
  - [ ] Old baselines deleted (keep last 30 days)

- [ ] **Backup & Recovery Plan**
  - [ ] Daily baseline backups
  - [ ] Weekly queue backups
  - [ ] Recovery procedure tested
  - [ ] Restore time < 1 hour

### Access Control

- [ ] **File Permissions Correct**
  ```bash
  ls -la config/baselines.json queue/ logs/
  # Expected: 600 (owner read/write only)
  ```

- [ ] **Environment Variables Protected**
  - [ ] OMNICOMPUTE_ENCRYPTION_KEY not exported globally
  - [ ] Only set at runtime
  - [ ] Not logged or printed

---

## Testing Phase (2-5 days before)

### Functional Testing

- [ ] **Telemetry Parser Works**
  ```bash
  python -c "
  from omnicompute.telemetry.parser import TelemetryParser
  parser = TelemetryParser()
  result = parser.parse(test_telemetry)
  assert len(result.metrics) > 0
  "
  ```

- [ ] **Baseline Cache Functional**
  ```bash
  python -c "
  from omnicompute.anomaly.baseline import BaselineCache
  cache = BaselineCache()
  baseline = cache.get('Sat-01', 'battery_soc_percent')
  assert baseline.mean > 0
  "
  ```

- [ ] **Anomaly Triager Works**
  ```bash
  python -c "
  from omnicompute.anomaly.triager import AnomalyTriager
  triager = AnomalyTriager()
  anomalies = triager.triage(test_metrics)
  assert any(a.severity == 'CRITICAL' for a in anomalies)
  "
  ```

- [ ] **Response Planner Works**
  ```bash
  python -c "
  from omnicompute.response.planner import ResponsePlanner
  planner = ResponsePlanner()
  actions = planner.plan(test_anomalies)
  assert any(a.action_type == 'load_shed' for a in actions)
  "
  ```

- [ ] **HITL Queue Functional**
  ```bash
  python -c "
  from omnicompute.queue.hitl import HumanReviewQueue
  queue = HumanReviewQueue()
  queue.add_escalation(test_escalation)
  assert queue.pending_count() > 0
  "
  ```

- [ ] **Uplink Bundler Works**
  ```bash
  python -c "
  from omnicompute.uplink.bundler import UplinkBundler
  bundler = UplinkBundler()
  bundle = bundler.create_bundle(test_data)
  assert bundle.is_encrypted
  assert len(bundle.payload) < 512000
  "
  ```

### Integration Testing

- [ ] **End-to-End Pipeline Works**
  ```bash
  python -c "
  from omnicompute.pipeline.orchestrator import Orchestrator
  orch = Orchestrator()
  results = orch.process_telemetry(test_batch)
  assert 'uplink_bundle' in results
  assert 'autonomous_actions' in results
  "
  ```

- [ ] **Graceful Degradation Tested**
  - [ ] Missing baseline: Uses nominal values ✓
  - [ ] Missing playbook: Escalates to HITL ✓
  - [ ] Encryption failure: Logs & continues ✓
  - [ ] Queue full: Trims low-risk items ✓

### Load Testing

- [ ] **High Volume Processing**
  ```bash
  python -c "
  # Generate 1000 telemetry items
  # Process all in one batch
  # Verify: <500ms total latency
  "
  ```

- [ ] **Memory Under Load**
  ```bash
  # Monitor memory while processing large batch
  # Expected: <500MB peak
  ```

- [ ] **Compression Efficiency**
  ```bash
  # Generate 1MB of telemetry
  # Compress and encrypt
  # Expected: 200-400KB output (40-70% reduction)
  ```

---

## Deployment Phase (Day before)

### Final Verification

- [ ] **All Checklist Items Complete**
  - [ ] Infrastructure verified
  - [ ] Software tested
  - [ ] Configuration validated
  - [ ] Security audited

- [ ] **Go/No-Go Decision Made**
  - [ ] Technical: GO ☐ or NO-GO ☐
  - [ ] Security: GO ☐ or NO-GO ☐
  - [ ] Operations: GO ☐ or NO-GO ☐
  - [ ] Management: GO ☐ or NO-GO ☐

- [ ] **Deployment Plan Reviewed**
  - [ ] Rollout strategy defined
  - [ ] Rollback plan documented
  - [ ] Communication plan ready

### Pre-Launch Activities

- [ ] **Deployment Kit Prepared**
  ```
  ├── omnicompute-agent.tar.gz
  ├── config/nodes.yaml
  ├── config/baselines.json
  ├── config/playbooks/
  ├── scripts/deploy.sh
  ├── scripts/health_check.sh
  └── OPERATIONS.md (printed)
  ```

- [ ] **Team Briefing Completed**
  - [ ] All operators trained
  - [ ] Shift schedule established
  - [ ] Escalation procedures reviewed
  - [ ] Emergency contacts posted

- [ ] **Monitoring Set Up**
  - [ ] Dashboard configured
  - [ ] Alert thresholds set
  - [ ] Log aggregation running
  - [ ] Baseline tracking active

---

## Launch Phase (Day of deployment)

### Contact Window 1 (First Orbit)

- [ ] **Pre-Launch Checklist**
  ```
  ☐ Ground station operational
  ☐ Encryption key verified
  ☐ Bundles queued and ready
  ☐ HITL queue empty
  ☐ All systems nominal
  ```

- [ ] **Monitor First Processing**
  ```bash
  tail -f logs/autonomous_actions.jsonl
  # Watch: Parser success, anomalies detected, actions executed
  ```

- [ ] **First Bundle Transmitted**
  - [ ] Size < 512KB
  - [ ] Encrypted successfully
  - [ ] Transmission confirmed
  - [ ] MCH received & acknowledged

### Contact Windows 2-10 (First Day)

- [ ] **Stable Operations Confirmed**
  - [ ] No unexpected errors
  - [ ] Anomalies reasonable
  - [ ] False positive rate <10%
  - [ ] Queue manageable

- [ ] **Baseline Sync Working**
  - [ ] MCH sending updates
  - [ ] Baseline age <24h
  - [ ] Confidence scores improving

- [ ] **HITL Escalations Manageable**
  - [ ] Queue stable
  - [ ] No timeouts
  - [ ] Ground team keeping pace

### Day 2-7 (First Week)

- [ ] **All Systems Stable**
  - [ ] No critical incidents
  - [ ] Performance within spec
  - [ ] Team confident & trained

- [ ] **Issues Identified & Logged**
  - [ ] Any anomalies documented
  - [ ] Fixes prioritized
  - [ ] Patches prepared if needed

- [ ] **Sign-Off Complete**
  - [ ] Technical lead: _____________
  - [ ] Operations lead: _____________
  - [ ] Mission lead: _____________
  - [ ] Date: _____________

---

## Post-Deployment Phase (Week 2+)

### Ongoing Verification

- [ ] Weekly baseline audits pass
- [ ] Monthly security audits clean
- [ ] Quarterly performance optimization complete
- [ ] No critical incidents

---

## Sign-Off

**This checklist MUST be signed off by:**

1. **Technical Lead** (code & system design)
   - Name: _____________
   - Date: _____________
   - Signature: _____________

2. **Operations Lead** (procedures & training)
   - Name: _____________
   - Date: _____________
   - Signature: _____________

3. **Security Lead** (encryption & compliance)
   - Name: _____________
   - Date: _____________
   - Signature: _____________

4. **Mission Lead** (approval to launch)
   - Name: _____________
   - Date: _____________
   - Signature: _____________

---

**Deployment Status: ☐ GO / ☐ NO-GO**

**If NO-GO, document blockers:**

```
Blocker 1: _______________
Priority: CRITICAL / HIGH / MEDIUM
Resolution: _______________
Target fix date: _______________

Blocker 2: _______________
[...]
```

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
