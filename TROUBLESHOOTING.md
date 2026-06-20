# Troubleshooting Guide

**OmniCompute Federated Infrastructure Agent**

Operational issues and how to resolve them.

---

## Installation & Setup

### Issue: ImportError: No module named 'omnicompute'

**Cause**: Virtual environment not activated or package not installed

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall package
pip install -e .

# Verify
python -c "from omnicompute.pipeline.orchestrator import Orchestrator; print('OK')"
```

### Issue: "ModuleNotFoundError: No module named 'cryptography'"

**Cause**: Dependencies not installed

**Solution**:
```bash
pip install -r requirements.txt
```

### Issue: Cannot create virtual environment

**Cause**: Python 3.10+ not available

**Solution**:
```bash
# Check Python version
python3 --version  # Must be 3.10+

# If not available, install:
brew install python@3.10  # macOS
apt-get install python3.10  # Ubuntu
```

---

## Configuration Issues

### Issue: "FileNotFoundError: config/nodes.yaml"

**Cause**: Configuration file not found

**Solution**:
```bash
# Copy example config
cp config/nodes.yaml.example config/nodes.yaml

# Edit with your nodes
nano config/nodes.yaml
```

### Issue: "Playbook not found: power_anomaly"

**Cause**: Playbook file doesn't exist or name mismatch

**Solution**:
```bash
# List available playbooks
ls -la config/playbooks/

# Check node config references correct names
grep playbooks config/nodes.yaml

# Copy example playbook to get started
cp config/playbooks/example_power_anomaly.yaml config/playbooks/power_anomaly.yaml
```

### Issue: "YAML parsing error in nodes.yaml"

**Cause**: Indentation or syntax error in YAML

**Solution**:
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config/nodes.yaml'))"

# Fix indentation (use spaces, not tabs)
# Each level should be 2 spaces:
#   satellites:
#     - id: Sat-01
#       node_type: leo_satellite
```

---

## Data & Baseline Issues

### Issue: "No baseline available for Sat-01"

**Cause**: First orbit (cold start) or baseline file missing

**Solution**:
```bash
# This is normal on first orbit - OmniCompute uses nominal values
# Baseline will accumulate over 30 days

# Check baseline file exists
ls -la config/baselines.json

# If missing, create empty:
echo "{}" > config/baselines.json

# Update baseline from ground after first contact window
# (MCH-Primary automatically syncs during contact window)
```

### Issue: "Baseline is stale (30+ days old)"

**Cause**: Baselines not updated from ground station

**Solution**:
```bash
# Check baseline age
jq '.["Sat-01"].battery_soc_percent.updated_at' config/baselines.json

# If stale, request baseline sync from MCH-Primary:
# 1. Contact Mission Control Hub
# 2. Request baseline refresh for your node
# 3. Wait for next contact window
# 4. Baselines auto-sync during uplink

# Or manually update (development only):
# Edit config/baselines.json with current stats
```

### Issue: "Baseline confidence low (age penalty)"

**Cause**: Baseline is old (7+ days)

**Severity**: Low confidence reduces autonomous action execution

**Solution**:
```bash
# Update baseline frequency
# MCH-Primary default: 24-hour updates
# For critical infrastructure: 12-hour updates

# Check baseline freshness
jq '.[] | .[] | .updated_at' config/baselines.json | sort

# Request more frequent updates from ground
```

---

## Anomaly Detection Issues

### Issue: "Too many false positives (nominal metrics flagged)"

**Cause**: Z-score threshold too low or baseline poor quality

**Solution**:
```bash
# Check current threshold (default: 2-sigma)
# See ARCHITECTURE.md for threshold explanation

# Options:
# 1. Wait 30 days for baseline to stabilize
# 2. Reduce anomaly confidence trigger threshold in playbooks
# 3. Adjust safe_ranges in config/nodes.yaml to be less strict

# Check baseline quality
jq '.["Sat-01"] | keys' config/baselines.json
```

### Issue: "Not detecting real anomalies"

**Cause**: Baseline poor quality, threshold too high, or playbook missing

**Solution**:
```bash
# 1. Check baseline exists for this metric
jq '.["Sat-01"].battery_soc_percent' config/baselines.json

# 2. Check playbook is assigned to node
grep -A 5 "id: Sat-01" config/nodes.yaml

# 3. Check trigger conditions
jq '.triggers' config/playbooks/power_anomaly.yaml

# 4. Check z-score calculation
# If z-score barely exceeds 2.0, increase min_confidence in playbook
```

### Issue: "Z-score calculation seems wrong"

**Cause**: Math verification needed

**Solution**:
```bash
# Z-score formula: (value - mean) / stddev
# Example:
# mean=65.0, stddev=8.0, value=14.2
# z = (14.2 - 65.0) / 8.0 = -6.35

# Verify in logs
tail -f logs/autonomous_actions.jsonl | jq '.[] | select(.node_id=="Sat-01") | {metric: .metric_name, z_score: .z_score}'
```

---

## Action Execution Issues

### Issue: "Action not executing (confidence too low)"

**Cause**: Action confidence < 0.75 threshold

**Solution**:
```bash
# Check confidence calculation
# action_confidence = anomaly_confidence × action.min_confidence

# Options:
# 1. Increase anomaly confidence (wait for better baseline)
# 2. Lower action.min_confidence in playbook
# 3. Check escalation queue for human decision

# Example: If anomaly.confidence=0.70, action.min_confidence=0.70
# Result: 0.70 × 0.70 = 0.49 (escalated)
# Fix: Lower action.min_confidence to 0.60
```

### Issue: "Action is irreversible but got executed"

**Cause**: Confidence was high enough to bypass escalation

**Solution**:
```bash
# Check action definition in playbook
jq '.actions[] | select(.reversible==false)' config/playbooks/power_anomaly.yaml

# For irreversible actions:
# - Must have reversible: false
# - Will escalate if confidence < 0.75
# - Will execute with log if confidence >= 0.75

# If you want stricter control:
# Increase min_confidence in playbook to force escalation
```

### Issue: "Playbook action failed, what happened?"

**Cause**: Action execution error or system issue

**Solution**:
```bash
# Check logs for failure reason
tail -f logs/autonomous_actions.jsonl | jq '.[] | select(.status=="FAILED")'

# Next action in sequence should execute
# If sequence fails entirely, alert_ground (fallback) is triggered

# Troubleshoot based on error message in logs
```

---

## Queue Issues

### Issue: "HITL queue is full (100 items)"

**Cause**: Too many escalations, slow ground response

**Solution**:
```bash
# Check queue size
jq '.pending_items | length' queue/hitl_review.json

# Triage high-priority items
jq '.pending_items | sort_by(.risk_level) | reverse' queue/hitl_review.json

# Ground station should:
# 1. Review CRITICAL items first
# 2. Send approval/rejection response
# 3. Low-risk items auto-trim when full

# To prevent:
# - Respond to escalations faster
# - Adjust action confidence thresholds
# - Reduce anomaly sensitivity
```

### Issue: "Escalation timed out but not executed"

**Cause**: Timeout logic or queue management

**Solution**:
```bash
# Check action timeout status
jq '.pending_items[] | select(.timeout_exceeded==true)' queue/hitl_review.json

# For timeout expiration:
# - If confidence > 0.75: execute with audit log
# - If confidence < 0.75: alert_ground, keep escalated

# Expected behavior:
# High-confidence actions execute after timeout
# Low-confidence stay escalated (can't force execution)
```

---

## Bundle Issues

### Issue: "Bundle exceeds 512KB limit"

**Cause**: Too much data in batch, compression ineffective

**Severity**: Uplink cannot be transmitted

**Solution**:
```bash
# Check bundle size
ls -lh output/uplink_bundle_*.json | tail -1

# Measure compression ratio
# If > 512KB:
# 1. Reduce batch size (more frequent contact windows)
# 2. Filter low-priority metrics (only send critical)
# 3. Manually trim old queue items before bundling

# Verify gzip is working
# Expected: 40-70% compression
# If <40%, data may be pre-compressed or random
```

### Issue: "Bundle encryption failed, sent unencrypted"

**Cause**: Missing or invalid encryption key

**Severity**: Medium (graceful degradation, logged)

**Solution**:
```bash
# Verify encryption key is set
echo $OMNICOMPUTE_ENCRYPTION_KEY

# If missing:
export OMNICOMPUTE_ENCRYPTION_KEY="your-base64-key"

# If invalid (not valid Fernet key):
# Generate new key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Verify bundle is encrypted
jq '.is_encrypted' output/uplink_bundle_*.json

# For classified deployments: CRITICAL
# Re-encrypt bundle before transmission
```

### Issue: "Bundle size varies wildly between contact windows"

**Cause**: Normal variation based on anomaly count and compression

**Solution**:
```bash
# Monitor bundle size over time
ls -l output/uplink_bundle_*.json | awk '{print $5}' | sort -n

# Expected:
# - Quiet orbits: 10-50KB
# - Active orbits: 100-300KB
# - Crisis orbits: 300-500KB

# If consistently near 512KB limit:
# Implement size management (filtering, batching)
```

---

## Performance Issues

### Issue: "Processing latency >1 second"

**Cause**: Large batch, slow baseline lookups, or CPU contention

**Solution**:
```bash
# Profile processing time
# Check logs for per-phase latency

# Typical:
# - Parse: <50ms
# - Triage: <50ms
# - Plan: <80ms
# - Bundle: <300ms

# If slow:
# 1. Check batch size (reduce if > 100 items)
# 2. Check baseline cache size (trim old entries)
# 3. Check CPU usage (may compete with other processes)

# Optimize:
# - Reduce playbook count
# - Pre-compile playbooks (cache YAML parsing)
# - Use faster disk for baseline cache
```

### Issue: "Memory usage >500MB"

**Cause**: Large baseline cache, many pending items, or memory leak

**Solution**:
```bash
# Monitor memory
watch -n 1 'ps aux | grep omnicompute'

# Check what's consuming memory
jq '. | length' config/baselines.json  # baseline size
jq '.pending_items | length' queue/hitl_review.json  # queue size

# Typical:
# - 50 nodes = ~50MB baselines
# - 100 items = ~5MB queue
# - Total: ~100-200MB

# If exceeding:
# 1. Trim old baseline entries (keep last 30 days only)
# 2. Clear old queue items (resolve escalations)
# 3. Check for memory leak (restart, check if memory grows again)
```

---

## Logging & Debugging

### Issue: "Not seeing logs"

**Cause**: Logs directory not created or logging not configured

**Solution**:
```bash
# Create logs directory
mkdir -p logs

# Check log files
ls -la logs/

# Tail recent logs
tail -f logs/autonomous_actions.jsonl

# If no logs appearing:
# 1. Verify OmniCompute is running
# 2. Check file permissions
# 3. Run with verbose logging
```

### Issue: "Logs contain sensitive data (PII)"

**Cause**: User input or credentials logged

**Severity**: Critical for compliance

**Solution**:
```bash
# Grep for PII patterns
grep -r "@" logs/  # emails
grep -r "password" logs/  # credentials

# OmniCompute should never log:
# - Email addresses
# - API keys
# - User credentials
# - Personal identifiers

# If found:
# 1. Redact logs immediately
# 2. Rotate any compromised credentials
# 3. Review logging code for compliance
```

---

## Contact & Escalation

**Can't resolve issue?**

1. Check [FAQ.md](FAQ.md) for common questions
2. Review [DEPLOYMENT.md](DEPLOYMENT.md) for setup procedures
3. Check logs for error details
4. Contact support: ashrafuzzmanhossain@gmail.com

**For production issues**:
- Alert Mission Control Hub immediately
- Provide node ID and timestamp
- Include relevant logs and configuration
- Prioritize based on severity

---

**Last Updated**: 2026-06-20  
**Version**: 1.0.0
