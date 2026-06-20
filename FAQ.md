# Frequently Asked Questions

**OmniCompute Federated Infrastructure Agent**

---

## General Questions

### What is OmniCompute?

OmniCompute is an autonomous monitoring and response system for distributed infrastructure across LEO satellites and forward-deployed ground nodes. It detects anomalies, makes decisions using playbooks, and escalates complex issues to humans.

**Key capabilities**:
- Autonomous anomaly detection (2-sigma Z-score)
- Playbook-driven response planning
- Human-in-the-loop escalation (HITL)
- FIPS-140-2 encrypted uplink bundles
- Power budget enforcement
- Graceful degradation during network blackout

### When should I use OmniCompute?

Use OmniCompute when you need to:
- Monitor distributed infrastructure with intermittent connectivity
- Make autonomous decisions without constant ground contact
- Enforce power and operational constraints
- Maintain audit trails for compliance
- Support ITAR-classified deployments

**Not suitable for**:
- Real-time systems requiring <100ms latency
- Systems with continuous, reliable network
- Applications needing complex ML models
- Streaming data pipelines

### What are the hardware requirements?

**Satellites**:
- Python 3.10+
- 2GB RAM minimum
- 15W power budget (typical LEO satellite)
- Contact window: 5-12 minutes per orbit

**Ground Nodes**:
- Python 3.10+
- 8GB RAM recommended
- 50W+ power budget
- Reliable network (but can tolerate brief outages)

**Mission Control Hub**:
- Python 3.10+
- 64GB RAM recommended
- Full network connectivity
- Always-on availability

---

## Deployment Questions

### How do I add a new satellite to my constellation?

1. Add node to `config/nodes.yaml`:
```yaml
satellites:
  - id: Sat-04
    node_type: leo_satellite
    contact_window_minutes: 8
    power_budget_watts: 15
    ram_gb: 2
    safe_ranges:
      battery_soc_percent: [10, 100]
      thermal_temp_celsius: [-50, 85]
    playbooks:
      - power_anomaly
      - thermal_violation
```

2. Assign playbooks (must exist in `config/playbooks/`)
3. Deploy OmniCompute to satellite
4. Verify first contact window communicates baselines
5. Monitor first 3 orbits for initial learning period

### How do I customize safe ranges?

Edit `config/nodes.yaml` for each node:

```yaml
safe_ranges:
  battery_soc_percent: [10, 100]      # Min-max range
  thermal_temp_celsius: [-50, 85]     # Will trigger CRITICAL if exceeded
  rf_signal_strength_dbm: [-120, -30] # Add metrics that matter to your hw
```

**Violations trigger CRITICAL severity anomalies immediately.**

### How do I create a new playbook?

1. Copy `config/playbooks/example_power_anomaly.yaml`
2. Customize:
   - `anomaly_type`: What triggers this playbook
   - `triggers`: Severity + z-score conditions
   - `actions`: Response actions in priority order
   - `modifiers`: Context-based adjustments (eclipse, degradation)
3. Add test cases
4. Assign to nodes in `config/nodes.yaml`
5. Test in development first

See [DEPLOYMENT.md](DEPLOYMENT.md) for full playbook guide.

### How do I manage encryption keys?

1. Generate key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

2. Store securely:
```bash
export OMNICOMPUTE_ENCRYPTION_KEY="your-base64-key"
```

3. Rotate between contact windows:
   - Store old key until all bundles decrypted
   - Switch to new key for next uplink
   - Test rotation on ground node first

**Never hardcode keys in source code.**

---

## Operational Questions

### What does "CRITICAL" severity mean?

**CRITICAL anomalies**:
- Z-score > 3.0 (very rare, statistical outlier)
- OR metric exceeds safe range (hard constraint violation)
- Require immediate action or escalation
- Never ignored

**Examples**:
- Battery SOC < 10% (hard limit)
- Thermal > 85°C (hardware damage risk)
- Power draw anomaly causing immediate shutdown

### How does confidence scoring work?

**Action confidence** = anomaly_confidence × playbook_action.min_confidence

Example:
- Anomaly detected with 0.90 confidence
- Playbook action requires 0.60 min confidence
- Action confidence = 0.90 × 0.60 = 0.54 (below 0.75 threshold → escalate)

**Escalation threshold**: 0.75 confidence
- Below 0.75 → escalate to HITL for human review
- Above 0.75 → execute autonomously (if reversible)

### What happens if a playbook fails?

1. **Graceful degradation**: Action logged, next action attempted
2. **Fallback action**: Execute final action (usually `alert_ground`)
3. **Queue escalation**: If irreversible, escalate to HITL
4. **Audit trail**: All failures logged with context

OmniCompute never stops working — it degrades gracefully.

### What if there's no baseline?

**First orbit (cold start)**:
1. No baseline exists (hasn't accumulated 30 days)
2. OmniCompute uses **nominal values** from config
3. All anomalies compared to nominal, not baseline
4. Less precise detection, but system still runs
5. After 30 days, baseline stabilizes and precision improves

**Missing metrics**:
- Skipped in anomaly detection
- Logged as degraded mode
- Continue with other metrics

### What does a 3-hour HITL timeout mean?

**For irreversible actions**:
1. Escalated to human review queue
2. Waits 3 hours for ground response
3. If no response:
   - High confidence (>0.75) → execute with log
   - Low confidence (<0.75) → alert ground, wait longer

**Rationale**: Satellite can't wait forever for contact window; better to execute high-confidence action with audit trail than remain stuck.

### How full can the HITL queue get?

**Queue capacity**: 100 items maximum

**Trimming strategy** (when full):
- Keep CRITICAL/ESCALATED items forever
- Trim oldest low-risk (INFO/WARNING) items first
- Never drop critical items

**Prevention**:
- Monitor queue size
- Respond to escalations promptly
- Adjust playbook confidence thresholds if queue fills

---

## Troubleshooting Questions

### How do I debug an anomaly?

Check the decision trace in logs:

```bash
tail -f logs/autonomous_actions.jsonl | jq '.[] | select(.node_id=="Sat-01")'
```

Look for:
1. **Anomaly detected**: Z-score, severity, confidence
2. **Playbook matched**: Which playbook triggered
3. **Actions proposed**: What was decided
4. **Actions executed**: What actually ran

Compare against `config/baselines.json` to verify baseline stats.

### Why isn't my playbook triggering?

1. **Trigger mismatch**: Check `anomaly_type` matches your metric
2. **Severity too low**: Anomaly is WARNING but trigger requires CRITICAL
3. **Z-score bounds**: Anomaly outside min/max_z_score range
4. **Playbook not assigned**: Check `config/nodes.yaml` playbooks list
5. **Missing playbook file**: Verify file exists in `config/playbooks/`

Run diagnostic:
```bash
# Check what playbooks are assigned
grep -A 10 "id: Sat-01" config/nodes.yaml | grep playbooks

# Verify playbook file exists
ls -la config/playbooks/
```

### What if bundle exceeds 512KB?

**Causes**:
- Too many anomalies + actions in batch
- Large queue of pending items
- Compression ratio worse than expected (rare)

**Solutions**:
1. **Increase contact window frequency** → more frequent smaller bundles
2. **Trim queue manually** → delete oldest low-risk items
3. **Filter metrics** → only send critical metrics to ground
4. **Verify compression** → check gzip is working (should be 40-70% reduction)

If bundle consistently oversized, investigate:
```bash
# Check bundle size
du -h output/uplink_bundle_*.json | sort -h | tail -5

# Check compression ratio
ls -la output/ | grep bundle
```

### How do I interpret baseline age penalty?

**Confidence decreases if baseline is stale**:
- Fresh baseline (< 7 days): No penalty
- 7-14 days old: 10% confidence reduction
- 14-30 days old: 20% confidence reduction
- 30+ days old: 30% confidence reduction (update baseline!)

**Prevention**:
- Update baselines every 24-48 hours
- Check baseline freshness in logs
- Alert ground if baseline hasn't updated

---

## Performance Questions

### What's the expected latency?

**Per component**:
- Parsing: <50ms
- Triage: <50ms
- Planning: <80ms
- Bundling: <300ms
- **Total**: <500ms per batch

**Bundle generation**: 1-10 seconds depending on size

**Contact window**: 8-12 minutes for full sync

### How much CPU/memory does OmniCompute use?

**Memory**:
- Baseline cache: ~50MB for 50 nodes
- HITL queue: ~5MB (max 100 items)
- Playbooks: ~10MB (typical 20-50 playbooks)
- **Total**: ~100MB typical, <500MB worst-case

**CPU**:
- Idle: <1% (event-driven)
- During processing: 5-20% (short bursts)
- Compression: 10-30% (during bundling)

### What compression ratio should I expect?

**Typical**: 40-70% reduction
- JSON telemetry: 50-60% (highly repetitive)
- Binary data: 10-30% (pre-compressed)
- Mixed: 40-50% (typical)

If compression ratio is below 40%, check:
- Data format (binary data compresses poorly)
- Repetition in JSON (well-structured data compresses better)
- Gzip library version (older versions compress less)

---

## Compliance Questions

### Is OmniCompute FIPS-140-2 compliant?

**Yes**, uses Fernet encryption from `cryptography` library, which is FIPS-140-2 Level 1 compliant.

**To enable**:
```bash
export OMNICOMPUTE_ENCRYPTION_KEY="your-base64-key"
```

**To verify**:
- Check bundle is encrypted in logs: `is_encrypted: true`
- Verify `encryption_algorithm: "Fernet"`
- Never send unencrypted bundles for classified data

### How do I ensure ITAR compliance?

**OmniCompute supports ITAR-classified nodes**:

1. Mark nodes as classified in `config/nodes.yaml`:
```yaml
ground_nodes:
  - id: FGN-Alpha
    classified: true  # ITAR compliance flag
```

2. Enable encryption (FIPS-140-2):
```bash
export OMNICOMPUTE_ENCRYPTION_KEY="..."
```

3. Verify in logs:
- All classified nodes have `is_encrypted: true`
- Bundles routed only to classified uplink channels
- No PII logged (check logs/autonomous_actions.jsonl)

4. Audit:
- Monthly review of bundle encryption status
- Verify no classified data in unclassified channels
- Check audit logs for compliance

---

## Support

**Still stuck?** Check these resources:

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Operational issues
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment procedures
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development setup
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- GitHub Issues: [https://github.com/AshraHossain/omnicompute-agent/issues](https://github.com/AshraHossain/omnicompute-agent/issues)

**Email**: ashrafuzzmanhossain@gmail.com

---

**Last Updated**: 2026-06-20  
**Version**: 1.0.0
