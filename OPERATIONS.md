# Operations Runbook

**OmniCompute Federated Infrastructure Agent — Daily Operations Guide**

For Mission Control Hub operators and satellite ground station teams.

---

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring & Health Checks](#monitoring--health-checks)
3. [Incident Response](#incident-response)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Emergency Procedures](#emergency-procedures)
6. [Escalation Procedures](#escalation-procedures)

---

## Daily Operations

### Morning Shift Start (UTC)

**Checklist:**
```
☐ 1. Verify Mission Control Hub connectivity
☐ 2. Check baseline cache freshness (should be <24 hours old)
☐ 3. Review overnight HITL escalations
☐ 4. Confirm all 6 satellites visible in next contact windows
☐ 5. Check uplink bundle queue (should be <10 items)
☐ 6. Verify encryption keys are rotated (monthly)
```

**Commands:**
```bash
# Check MCH connectivity
curl -s http://localhost:8000/health

# Verify baseline freshness
jq '.[] | .battery_soc_percent.updated_at' config/baselines.json | sort | tail -1

# Review escalations
jq '.pending_items | length' queue/hitl_review.json
jq '.pending_items | sort_by(.timeout_utc) | reverse' queue/hitl_review.json

# Next contact windows
grep "contact_window_minutes\|id:" config/nodes.yaml | paste - -

# Bundle queue depth
ls -1 output/uplink_bundle_*.json | wc -l
```

### Contact Window Execution (Every ~94 minutes for satellites)

**Pre-Contact Checklist:**
```
☐ 1. Verify ground station RF equipment operational
☐ 2. Confirm satellite ephemeris is current
☐ 3. Check power budget available
☐ 4. Ensure uplink path is clear
☐ 5. Verify encryption key is loaded
```

**During Contact Window:**
```bash
# Stream logs in real-time
tail -f logs/autonomous_actions.jsonl | jq '.[] | {timestamp, node_id, anomalies_detected, actions_executed}'

# Monitor bundle transmission
watch -n 1 'ls -lh output/uplink_bundle_*.json | tail -5'

# Track queue changes
watch -n 5 'jq ".pending_items | length" queue/hitl_review.json'
```

**Post-Contact Window:**
```bash
# Archive uplink bundle
mv output/uplink_bundle_*.json archive/uplink/$(date +%Y%m%d_%H%M%S)/

# Extract transmission status
jq '.[] | select(.status=="BUNDLED") | {timestamp, node_id, bundle_size_bytes}' logs/autonomous_actions.jsonl | tail -20

# Verify all CRITICAL items transmitted
jq '.[] | select(.severity=="CRITICAL") | {node_id, action, status}' logs/autonomous_actions.jsonl | tail -10
```

### End of Shift Handoff (Every 8 hours)

**Handoff Checklist:**
```
☐ 1. Summarize unresolved escalations
☐ 2. Note any baseline anomalies (stale/missing)
☐ 3. Report bundle transmission success rate
☐ 4. Flag any playbooks that underperformed
☐ 5. Document any manual interventions
```

**Handoff Report Template:**
```markdown
## Shift Handoff - [DATE] [TIME UTC]

### Overview
- Satellites visible: 6/6
- Contact windows completed: X/X
- Bundles transmitted: X
- Transmission success rate: XX%

### Escalations
- Pending human review: X items
- Average time in queue: X hours
- Oldest escalation timeout: [TIME]

### Baselines
- Fresh (<24h): X nodes
- Stale (>7 days): X nodes
- Missing: X nodes

### Performance
- Anomalies detected: X
- Actions executed: X
- Avg confidence: XX%

### Issues
- [Any unusual patterns or failures]

### Recommended Actions
- [For incoming shift]
```

---

## Monitoring & Health Checks

### Real-Time Monitoring

**Dashboard Commands:**
```bash
# Overall system health (run every minute)
watch -n 60 '
echo "=== OMNICOMPUTE HEALTH ===";
echo "Satellites online: $(jq "keys | length" config/baselines.json)";
echo "HITL queue: $(jq ".pending_items | length" queue/hitl_review.json)";
echo "Recent anomalies: $(jq "[.[] | select(.severity==\"CRITICAL\")] | length" logs/autonomous_actions.jsonl | tail -100)";
echo "Baseline age (days): $(jq ".[] | .battery_soc_percent.updated_at" config/baselines.json | xargs -I {} date -d {} +%s | xargs -I {} echo "scale=1; ($(date +%s) - {}) / 86400" | bc)";
'
```

**Component Health Checks:**
```bash
# Parser health (should process <100ms)
tail -100 logs/autonomous_actions.jsonl | jq '[.[] | select(.component=="parser") | .latency_ms] | add / length'

# Baseline cache health (should have <2% missing)
jq '[.[] | .battery_soc_percent] | map(select(. != null)) | length / 6 * 100' config/baselines.json

# Triager health (should flag <5% anomalies in nominal conditions)
tail -1000 logs/autonomous_actions.jsonl | jq '[.[] | select(.severity=="NOMINAL")] | length / length * 100'

# Queue health (should not exceed 100 items)
jq '.pending_items | length' queue/hitl_review.json
```

### Baseline Quality Monitoring

**Weekly Baseline Audit:**
```bash
#!/bin/bash
echo "=== BASELINE AUDIT ==="

jq -r 'to_entries[] | .key' config/baselines.json | while read node; do
  echo ""
  echo "Node: $node"
  
  # Check all required metrics present
  metrics=$(jq ".$node | keys" config/baselines.json | tr -d '[]" \n' | tr ',' '\n' | sort | tr '\n' ',' | sed 's/,$//')
  echo "  Metrics: $metrics"
  
  # Check age
  age=$(jq ".$node | .battery_soc_percent.updated_at" config/baselines.json | xargs -I {} date -d {} +%s | xargs -I {} echo "scale=0; ($(date +%s) - {}) / 86400" | bc)
  echo "  Age: ${age} days"
  
  # Check stddev (should be >0.5)
  stddev=$(jq ".$node.battery_soc_percent.stddev" config/baselines.json)
  if (( $(echo "$stddev < 0.5" | bc -l) )); then
    echo "  ⚠️  LOW STDDEV: $stddev (data may be too uniform)"
  fi
done
```

### Anomaly Pattern Detection

**Weekly Pattern Review:**
```bash
# What anomalies are most common?
jq '[.[] | .metric_name] | group_by(.) | map({metric: .[0], count: length}) | sort_by(.count) | reverse' logs/autonomous_actions.jsonl | head -20

# Which nodes are noisiest (most anomalies)?
jq '[.[] | .node_id] | group_by(.) | map({node: .[0], count: length}) | sort_by(.count) | reverse' logs/autonomous_actions.jsonl | head -10

# Which playbooks are underperforming (<70% success)?
jq '[.[] | select(.playbook_matched != null) | .playbook_matched] | group_by(.) | map({playbook: .[0], count: length})' logs/autonomous_actions.jsonl
```

---

## Incident Response

### Incident: High False Positive Rate

**Symptoms:**
- NOMINAL metrics flagged as WARNING/CRITICAL
- Baseline age penalty visible in logs
- Confidence scores artificially low

**Response:**
```bash
# 1. Check baseline age
jq '.[] | .battery_soc_percent.updated_at' config/baselines.json | sort | head -1
# If >7 days old, request baseline refresh from ground

# 2. Check baseline quality
jq '.[] | .battery_soc_percent | {mean, stddev}' config/baselines.json
# If stddev <1.0, baseline may be too tight

# 3. Review anomaly triggers
grep -A 5 "min_z_score" config/playbooks/*.yaml
# Adjust triggers if z_score < 2.5

# 4. Monitor recovery
jq '[.[] | select(.severity=="CRITICAL")] | length' logs/autonomous_actions.jsonl | tail -100
# Should drop to <5% within 24 hours
```

### Incident: HITL Queue Filling Up

**Symptoms:**
- Queue >50 items
- Escalations aging without resolution
- New escalations being trimmed

**Response:**
```bash
# 1. Check queue depth and age
jq '.pending_items | sort_by(.timeout_utc) | [{oldest: .[0].timeout_utc, newest: .[-1].timeout_utc, count: length}]' queue/hitl_review.json

# 2. Identify bottleneck
jq '.pending_items | group_by(.node_id) | map({node: .[0].node_id, count: length}) | sort_by(.count) | reverse' queue/hitl_review.json

# 3. Triage by risk
jq '.pending_items | sort_by(.risk_level) | reverse' queue/hitl_review.json | head -20

# 4. Process high-risk items first
# Manually review items with risk_level="CRITICAL" or "HIGH"

# 5. Execute timed-out items if confidence >0.75
jq '.pending_items[] | select(.timeout_exceeded==true and .action_confidence>0.75)' queue/hitl_review.json
```

### Incident: Bundle Exceeds 512KB

**Symptoms:**
- Uplink bundle cannot be transmitted
- Contact window ending without successful uplink
- Bundle size consistently >500KB

**Response:**
```bash
# 1. Check recent bundle sizes
ls -lh output/uplink_bundle_*.json | tail -10

# 2. Measure compression ratio
for f in output/uplink_bundle_*.json; do
  original=$(jq '.raw_size_bytes' "$f" 2>/dev/null || du -b "$f" | awk '{print $1}')
  compressed=$(du -b "$f" | awk '{print $1}')
  echo "$f: $original -> $compressed bytes"
done

# 3. Identify what's inflating bundles
jq '.[] | {timestamp, component, size_bytes}' logs/autonomous_actions.jsonl | sort -k3 -rn | head -20

# 4. Reduce bundle size
# Option A: Trim old queue items
jq '.pending_items |= map(select(.risk_level != "INFO" and .risk_level != "WARNING"))' queue/hitl_review.json

# Option B: Filter non-critical metrics
# Edit config/nodes.yaml to only send critical metrics

# Option C: Increase contact window frequency
# Request more frequent contact windows from Ground Operations
```

### Incident: Encryption Key Rotation Failed

**Symptoms:**
- Bundle with `is_encrypted: false`
- OMNICOMPUTE_ENCRYPTION_KEY missing or invalid
- ITAR compliance flag triggered

**Response:**
```bash
# 1. Verify key is set
echo $OMNICOMPUTE_ENCRYPTION_KEY
# If empty, export new key immediately

# 2. Generate fresh key (if compromised)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Validate key format
python3 -c "
from cryptography.fernet import Fernet
try:
    Fernet(b'$OMNICOMPUTE_ENCRYPTION_KEY')
    print('✓ Key is valid')
except:
    print('✗ Key is INVALID')
"

# 4. Re-encrypt any unencrypted bundles
# Do NOT transmit unencrypted classified data
# Flag bundles for re-encryption and re-transmission

# 5. Update key rotation schedule
# Current: Monthly
# Consider: Weekly (for classified deployments)
```

---

## Maintenance Procedures

### Weekly Baseline Refresh

**When to refresh:**
- Every 7 days (or immediately if data quality issues detected)
- When major operational change occurs (e.g., satellite reconfiguration)
- When baseline age penalty exceeds 10% confidence loss

**Procedure:**
```bash
# 1. Notify MCH-Primary of baseline refresh request
echo "BASELINE_REFRESH_REQUEST: All nodes" | nc mch-primary 5000

# 2. Wait for MCH response (next contact window)

# 3. Verify new baselines received
jq '.[] | .battery_soc_percent.updated_at' config/baselines.json | xargs -I {} date -d {} '+%s'

# 4. Confirm age penalty cleared
jq '.[] | {node: .node_id, age_days: "CALCULATED"}' config/baselines.json
```

### Monthly Security Audit

**Checklist:**
```
☐ 1. Rotate encryption keys (if not automated)
☐ 2. Audit logs for PII (grep "@" logs/*)
☐ 3. Verify ITAR compliance (all classified=true nodes encrypted)
☐ 4. Check for hardcoded credentials (grep -r "password\|token\|key" .)
☐ 5. Review audit trail for unusual patterns
☐ 6. Validate file permissions (logs should be 0600)
```

**Commands:**
```bash
# Audit logs for PII
grep -r "@\|password\|token\|key" logs/ --ignore-case

# Check ITAR compliance
jq '[.[] | select(.classified==true)] | map(.id)' config/nodes.yaml | \
xargs -I {} bash -c "grep -l '\"{}\"' output/uplink_bundle_*.json | xargs grep 'is_encrypted: false'"

# Validate file permissions
chmod 600 logs/*.jsonl
chmod 600 queue/*.json
chmod 600 config/baselines.json
```

### Quarterly Performance Optimization

**Review & Optimize:**
```bash
# 1. Analyze latency by component
jq '[.[] | {parser_ms, triage_ms, planner_ms, bundle_ms}] | add as $totals | map(. / $totals * 100)' logs/autonomous_actions.jsonl | head -50

# 2. Identify slow nodes
jq '[.[] | .node_id] | group_by(.) | map({node: .[0], avg_latency: ([.[] | latency] | add / length)})' logs/autonomous_actions.jsonl | sort_by(.avg_latency) | reverse | head -5

# 3. Check memory footprint
ps aux | grep omnicompute | grep -v grep

# 4. Archive old logs (keep last 90 days)
find logs/ -name "*.jsonl" -mtime +90 -exec gzip {} \;

# 5. Verify compression efficiency
du -sh archive/
```

---

## Emergency Procedures

### Emergency: Satellite Communication Lost

**Immediate Actions:**
```
☐ 1. Verify ground station RF equipment (not a comms failure)
☐ 2. Update ephemeris (satellite may be drifting)
☐ 3. Switch to backup ground station (if available)
☐ 4. Disable that satellite from responding until contact restored
```

**Commands:**
```bash
# Remove node from active config temporarily
jq 'del(.satellites[] | select(.id=="Sat-XX"))' config/nodes.yaml > config/nodes.yaml.bak
mv config/nodes.yaml.bak config/nodes.yaml

# Mark in logs
echo "{\"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"event\": \"COMMS_LOST\", \"node_id\": \"Sat-XX\"}" >> logs/incidents.jsonl
```

### Emergency: Baseline Cache Corrupted

**Immediate Actions:**
```
☐ 1. Stop processing (prevent making decisions on bad baselines)
☐ 2. Request baseline restore from MCH-Primary
☐ 3. Use nominal values as fallback
☐ 4. Log incident for audit trail
```

**Commands:**
```bash
# Restore from backup (if available)
cp archive/baselines/latest.json config/baselines.json

# Or initialize with nominal values
python3 << 'PYTHON'
import json
nodes = ["Sat-01", "Sat-02", "Sat-03", "FGN-Alpha", "FGN-Bravo", "FGN-Charlie"]
nominal = {
    node: {
        "battery_soc_percent": {"mean": 65.0, "stddev": 10.0, "updated_at": "NOMINAL"},
        "thermal_temp_celsius": {"mean": 25.0, "stddev": 5.0, "updated_at": "NOMINAL"},
    }
    for node in nodes
}
with open("config/baselines.json", "w") as f:
    json.dump(nominal, f, indent=2)
PYTHON
```

### Emergency: Power Budget Exceeded

**Immediate Actions:**
```
☐ 1. Pause non-critical actions
☐ 2. Log incident with node_id and timestamp
☐ 3. Alert MCH-Primary for next contact
☐ 4. Review playbook power costs (may be underestimated)
```

**Commands:**
```bash
# Check power budget remaining
jq '.[] | select(.power_remaining_watts < 2)' logs/autonomous_actions.jsonl

# Disable expensive actions temporarily
jq '.playbooks |= map(select(.action_type != "maximize_solar"))' config/nodes.yaml

# Log incident
echo "{\"incident\": \"POWER_BUDGET_EXCEEDED\", \"node\": \"Sat-XX\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> logs/incidents.jsonl
```

---

## Escalation Procedures

### When to Escalate to Mission Control

**CRITICAL Issues (Escalate Immediately):**
- Satellite not responding for >2 contact windows
- Bundle encryption failed (classified data)
- Baseline cache corrupted
- >50 items in HITL queue
- Power budget exceeded on 3+ nodes

**HIGH Priority (Escalate Within 1 Hour):**
- Playbook success rate <70%
- Baseline age >14 days
- False positive rate >20%
- Bundle consistently oversized

**MEDIUM Priority (Escalate Within 4 Hours):**
- Baseline age >7 days
- Single node acting anomalous
- Slow performance trend

**Escalation Template:**
```
TO: Mission Control Hub (MCH-Primary)
PRIORITY: [CRITICAL|HIGH|MEDIUM]
TIMESTAMP: [UTC]
AFFECTED_NODES: [List]
DESCRIPTION: [Brief summary]
SUPPORTING_DATA: [jq query or log excerpt]
RECOMMENDED_ACTION: [What MCH should do]
TIMEOUT: [When decision needed]
```

---

## Contact & Support

**Operational Support:**
- 📞 Ground Station Lead: [Contact]
- 📧 MCH Duty Officer: mch-primary@mission.gov
- 🚨 Emergency Line: [Number]

**Technical Support:**
- 📧 Email: ashrafuzzmanhossain@gmail.com
- 🐛 Issues: https://github.com/AshraHossain/omnicompute-agent/issues
- 📖 Documentation: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
