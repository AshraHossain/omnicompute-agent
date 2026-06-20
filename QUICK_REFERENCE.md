# Quick Reference

**OmniCompute Federated Infrastructure Agent — One-Pager**

---

## Installation

```bash
git clone https://github.com/AshraHossain/omnicompute-agent.git
cd omnicompute-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

### Copy example configs:
```bash
cp config/nodes.yaml.example config/nodes.yaml
cp config/playbooks/example_power_anomaly.yaml config/playbooks/power_anomaly.yaml
```

### Edit for your infrastructure:
```yaml
satellites:
  - id: Sat-01
    power_budget_watts: 15
    safe_ranges:
      battery_soc_percent: [10, 100]
      thermal_temp_celsius: [-50, 85]
    playbooks:
      - power_anomaly
```

---

## Running OmniCompute

### Process telemetry batch:
```python
from omnicompute.pipeline.orchestrator import Orchestrator

orch = Orchestrator()
results = orch.process_telemetry(telemetry_batch)
# outputs: uplink_bundle, hitl_queue, autonomous_actions.jsonl
```

### Check status:
```bash
# View logs
tail -f logs/autonomous_actions.jsonl

# Check queue
jq '.pending_items | length' queue/hitl_review.json

# Monitor bundle size
ls -lh output/uplink_bundle_*.json | tail -1
```

---

## Key Concepts

| Concept | Meaning |
|---------|---------|
| **Z-score** | Statistical deviation from 30-day baseline (2-sigma = anomaly) |
| **Severity** | CRITICAL (>3σ), WARNING (2-3σ), NOMINAL (<2σ) |
| **Confidence** | Anomaly confidence × playbook action confidence = execution confidence |
| **Escalation** | If confidence < 0.75, route to HITL queue for human review |
| **3-hour HITL timeout** | If escalation unresolved after 3 hours: execute (conf>0.75) or alert ground (conf<0.75) |
| **Power budget** | Max watts per node per contact window (enforce with 5% margin) |
| **Contact window** | 8-12 minutes of connectivity per satellite orbit (~94 min cycle) |

---

## Playbooks

### Add a new playbook:

1. Create `config/playbooks/new_playbook.yaml`
2. Define anomaly_type, triggers, actions, modifiers
3. Assign to nodes in `config/nodes.yaml`

### Playbook structure:
```yaml
name: power_anomaly
anomaly_type: battery_soc_percent
triggers:
  - metric: battery_soc_percent
    severity: CRITICAL
    min_z_score: 3.0
actions:
  - action_type: load_shed
    reversible: true
    min_confidence: 0.6
modifiers:
  - when: eclipse
    effect: aggressive_load_shed
    multiplier: 1.5
```

---

## Baselines

### Format (`config/baselines.json`):
```json
{
  "Sat-01": {
    "battery_soc_percent": {
      "mean": 65.0,
      "stddev": 8.0,
      "updated_at": "2026-06-20T12:00:00Z"
    }
  }
}
```

### Update baselines:
- MCH-Primary syncs automatically (24-hour default)
- Manual update for development:
  ```bash
  # Compute baseline from telemetry
  python -c "
  import json
  from statistics import mean, stdev
  data = [65, 64, 66, 68, 62, 70, 69, 67, 63, 65] * 3  # 30 days
  print(json.dumps({'mean': mean(data), 'stddev': stdev(data)}, indent=2))
  "
  ```

---

## Confidence Scoring

```
action_confidence = anomaly_confidence × action.min_confidence

Example:
- Anomaly detected with 0.90 confidence
- Action requires 0.60 min confidence
- Result: 0.90 × 0.60 = 0.54 (below 0.75 → escalate)
```

---

## Testing

```bash
# Run all tests
pytest src/omnicompute/tests/ -v

# Check coverage
pytest --cov=src/omnicompute --cov-report=term

# Run single test file
pytest src/omnicompute/tests/test_pipeline_orchestrator.py -v

# Watch mode
pytest-watch src/omnicompute/tests/ -- -v
```

**Target**: 80%+ coverage (currently 97%)

---

## Encryption

### Generate key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Enable encryption:
```bash
export OMNICOMPUTE_ENCRYPTION_KEY="your-base64-key"
```

### Verify in logs:
```bash
tail -f logs/autonomous_actions.jsonl | jq '.[] | {timestamp, is_encrypted, encryption_algorithm}'
```

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| No baseline for node | `jq '.["Sat-01"]' config/baselines.json` |
| Playbook not triggering | `grep "id: Sat-01" config/nodes.yaml \| grep playbooks` |
| Bundle exceeds 512KB | `ls -lh output/uplink_bundle_*.json \| tail -1` |
| HITL queue full | `jq '.pending_items \| length' queue/hitl_review.json` |
| Anomalies not detected | Baseline age penalty, threshold too high, or playbook mismatch |

**See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for full guide.**

---

## File Structure

```
omnicompute-agent/
├── src/omnicompute/
│   ├── pipeline/          # Orchestrator
│   ├── telemetry/         # Parser
│   ├── anomaly/           # Baseline + Triager
│   ├── response/          # Planner
│   ├── queue/             # HITL Queue
│   ├── uplink/            # Bundler
│   └── tests/             # 155 tests (97% coverage)
├── config/
│   ├── nodes.yaml.example        # Node inventory
│   └── playbooks/
│       └── example_power_anomaly.yaml
├── logs/                  # autonomous_actions.jsonl
├── queue/                 # hitl_review.json
├── output/                # uplink_bundle_*.json
└── data/                  # telemetry_batch_*.json
```

---

## Common Commands

```bash
# Process telemetry
python -c "
from omnicompute.pipeline.orchestrator import Orchestrator
orch = Orchestrator()
orch.process_telemetry(batch_data)
"

# Check node health
jq '.[] | select(.node_id=="Sat-01")' logs/autonomous_actions.jsonl | tail -10

# Debug anomaly
jq '.[] | select(.metric_name=="battery_soc_percent") | {z_score, severity, confidence}' logs/autonomous_actions.jsonl

# List pending escalations
jq '.pending_items[] | {node_id, recommended_action, risk_level}' queue/hitl_review.json

# Monitor bundle compression
for f in output/uplink_bundle_*.json; do echo -n "$f: "; du -h "$f"; done
```

---

## Documentation Map

- [README.md](README.md) — Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [COMPONENTS.md](COMPONENTS.md) — Component details
- [FAQ.md](FAQ.md) — Frequently asked questions
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Operational issues
- [DEPLOYMENT.md](DEPLOYMENT.md) — Deployment procedures
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development setup
- [TESTING.md](TESTING.md) — Test suite
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines
- [SECURITY.md](SECURITY.md) — Security policy
- [CHANGELOG.md](CHANGELOG.md) — Version history
- [ROADMAP.md](ROADMAP.md) — Future features

---

## Support

- 📧 Email: ashrafuzzmanhossain@gmail.com
- 🐛 Issues: https://github.com/AshraHossain/omnicompute-agent/issues
- 💬 Discussions: https://github.com/AshraHossain/omnicompute-agent/discussions

---

**Version**: 1.0.0 | **Last Updated**: 2026-06-20
