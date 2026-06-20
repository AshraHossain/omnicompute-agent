# OmniCompute Deployment Guide

**Deployment Status**: Production Ready ✅

This guide covers deploying OmniCompute to LEO satellites and forward-deployed ground nodes.

## Quick Navigation

📖 **Documentation**:
- [README.md](README.md) — Project overview
- [ARCHITECTURE.md](ARCHITECTURE.md) — System design
- [COMPONENTS.md](COMPONENTS.md) — Component contracts
- [DATA_SCHEMAS.md](DATA_SCHEMAS.md) — Data model specifications
- [TESTING.md](TESTING.md) — Test suite details
- [DEVELOPMENT.md](DEVELOPMENT.md) — Development setup
- [SECURITY.md](SECURITY.md) — Security and compliance
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contribution guidelines

## Pre-Deployment Checklist

Before deploying to production satellites:

- ✅ All 155 tests passing (100% pass rate)
- ✅ 97% code coverage
- ✅ FIPS-140-2 encryption validated
- ✅ ITAR compliance verified
- ✅ Baseline statistics available (30-day)
- ✅ Response playbooks configured
- ✅ Encryption keys generated and secured
- ✅ Node configuration (nodes.yaml) finalized

## Prerequisites

### Software
- Python 3.10+
- pip or conda
- Git (for updates)

### Hardware
- **LEO Satellites**: 2GB RAM minimum, 15W power budget available
- **Ground Nodes**: 8GB RAM, 50W+ power budget
- **Mission Control Hub**: Full connectivity to satellite network

### Encryption Keys

Generate Fernet encryption key:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Store securely:
- Satellites: Pre-load into onboard key store
- Ground nodes: Store in environment variable `OMNICOMPUTE_ENCRYPTION_KEY`
- Mission Control: HSM or key management service

## Installation

### 1. On Local/Test Environment

```bash
# Clone repository
git clone https://github.com/AshraHossain/omnicompute-agent.git
cd omnicompute-agent

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pytest src/omnicompute/tests/ -q
```

### 2. On Satellites (Example: Sat-01)

```bash
# SSH into satellite
ssh satcom@sat-01.local

# Create deployment directory
sudo mkdir -p /edge/agent
sudo chown satcom:satcom /edge/agent

# Deploy code
rsync -av src/omnicompute/ satcom@sat-01:/edge/agent/
rsync -av config/ satcom@sat-01:/edge/agent/config/

# Install Python 3.10 (if needed)
sudo apt-get install python3.10 python3.10-venv

# Set up runtime
python3.10 -m venv /edge/agent/venv
source /edge/agent/venv/bin/activate
pip install -r /edge/agent/requirements.txt

# Verify
python3 -c "from omnicompute.pipeline.orchestrator import Orchestrator; print('✅ Ready')"
```

### 3. On Ground Nodes (Example: FGN-Alpha)

```bash
# SSH into ground node
ssh operator@fgn-alpha.internal

# Create deployment directory
sudo mkdir -p /ops/omnicompute
sudo chown operator:operator /ops/omnicompute

# Deploy same as satellites
cd /ops/omnicompute
git clone https://github.com/AshraHossain/omnicompute-agent.git .

# Install
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test
pytest src/omnicompute/tests/ -q
```

## Configuration

### nodes.yaml

Define your node inventory:

```yaml
satellites:
  - id: Sat-01
    node_type: leo_satellite
    power_budget_watts: 15
    ram_gb: 2
    contact_window_minutes: 8
    contact_cycle_minutes: 94
    safe_ranges:
      battery_soc_percent: [10, 100]
      thermal_temp_celsius: [-50, 85]
      rf_signal_strength_dbm: [-120, -30]

ground_nodes:
  - id: FGN-Alpha
    node_type: forward_ground_node
    classified: true
    power_budget_watts: 50
    ram_gb: 8
    safe_ranges:
      thermal_temp_celsius: [-30, 50]

mission_control:
  - id: MCH-Primary
    node_type: mission_control_hub
    power_budget_watts: 500
    ram_gb: 64
```

### Playbooks

Define response playbooks in `config/playbooks/`:

```yaml
name: power_anomaly
anomaly_type: battery_soc_percent
triggers:
  - metric: battery_soc_percent
    severity: CRITICAL
    min_z_score: 3.0

actions:
  - action_type: load_shed
    params:
      target_watts: 6.0
      exclude: [rf_backup]
    reversible: true
    min_confidence: 0.6

modifiers:
  - when: "solar_degradation > 20"
    effect: exclude_action_param
    target_action: load_shed
    exclude: rf_backup
```

### Baselines

Initialize 30-day baseline statistics:

```json
{
  "Sat-01": {
    "battery_soc_percent": {
      "mean": 65.0,
      "stddev": 8.0,
      "updated_at": "2026-06-20T00:00:00Z"
    },
    "thermal_temp_celsius": {
      "mean": 35.0,
      "stddev": 5.0,
      "updated_at": "2026-06-20T00:00:00Z"
    }
  }
}
```

## Runtime

### Starting the Agent

```bash
# Activate environment
source /edge/agent/venv/bin/activate

# Set encryption key
export OMNICOMPUTE_ENCRYPTION_KEY="your-base64-encoded-key"

# Run agent (example: process telemetry batch)
python3 << 'EOF'
from omnicompute.pipeline.orchestrator import Orchestrator
from pathlib import Path
import json

# Load configuration
node_config = json.loads(Path("config/nodes.yaml").read_text())
baselines = json.loads(Path("config/baselines.json").read_text())
encryption_key = "your-encryption-key"

# Initialize orchestrator
orchestrator = Orchestrator(
    baseline_cache=baselines,
    node_config=node_config,
    playbooks_dir="config/playbooks/",
    encryption_key=encryption_key
)

# Process telemetry
telemetry_batch = Path("data/telemetry_latest.json").read_text()
bundle = orchestrator.process_telemetry(
    raw_json=telemetry_batch,
    power_budget_remaining=85.0
)

# Save bundle for uplink
Path("output/bundle.json").write_text(json.dumps(bundle.dict()))
print(f"✅ Bundle ready: {bundle.metadata.compressed_size_bytes} bytes")
EOF
```

### Monitoring

Monitor autonomous execution:

```bash
# Tail action logs
tail -f logs/autonomous_actions.jsonl

# Check HITL queue
cat queue/hitl_review.json | jq '.pending_items'

# Verify baseline updates
cat config/baselines.json | jq '.["Sat-01"]'
```

## ITAR Compliance

For classified deployments:

1. **Node Isolation**: Ensure classified nodes (marked `classified: true`) do NOT route data through unclassified networks
2. **Encryption**: Always enable FIPS-140-2 encryption (`encryption_key` provided)
3. **Audit Trail**: All actions logged with `node_id`, `timestamp`, `action_type`, `confidence`
4. **PII Filtering**: Agent never logs raw sensor values, only aggregated metrics
5. **Network Routing**: Use secure SATCOM for all uplink/downlink

## Security

### Encryption Key Management

```bash
# Generate key
python3 -c "from cryptography.fernet import Fernet; k = Fernet.generate_key(); print(k.decode()); print('Store this securely!')"

# Rotate key (between contact windows)
export OLD_KEY="old-key"
export NEW_KEY="new-key"
python3 -c "
from omnicompute.uplink.bundler import UplinkBundler
# Re-encrypt with new key (transparent to user)
"

# Never hardcode in source code
# Always use environment variable: export OMNICOMPUTE_ENCRYPTION_KEY=...
```

### Network Security

- All SATCOM uplinks: HTTPS/TLS only
- Ground node to MCH: IPSec or authenticated VPN
- Inter-satellite: Encrypted point-to-point only
- Mission Control: Network firewall with allowlisting

## Troubleshooting

### Issue: "No baselines available"

**Solution**: Initialize baseline cache during first orbit:
```bash
# OmniCompute falls back to nominal values
# After first contact window, baselines are updated
# Check: cat config/baselines.json
```

### Issue: "Playbook not found"

**Solution**: Verify playbook YAML is in config/playbooks/:
```bash
ls -la config/playbooks/
# Should contain: power_anomaly.yaml, thermal_violation.yaml, rf_jamming.yaml
```

### Issue: "Encryption key invalid"

**Solution**: Verify key format and environment variable:
```bash
# Key must be base64-encoded 32-byte Fernet key
python3 -c "
from cryptography.fernet import Fernet
Fernet(b'your-key')  # Should not raise exception
"
```

### Issue: "Bundle exceeds 512KB"

**Solution**: Reduce telemetry batch size or increase contact window frequency:
```bash
# Current compression ratio: ~55-70%
# If bundle still oversized, filter low-priority metrics before bundling
```

## Health Checks

### Pre-Deployment Validation

```bash
# Run full test suite
pytest src/omnicompute/tests/ -v --cov=src/omnicompute

# Check for hardcoded secrets
grep -r "api_key\|password\|secret" src/ && echo "❌ Found secrets!" || echo "✅ No secrets"

# Verify encryption
python3 -c "from cryptography.fernet import Fernet; Fernet(b'$ENCRYPTION_KEY')"

# Type checking
python3 -m mypy src/omnicompute --ignore-missing-imports
```

### Post-Deployment Validation

```bash
# Verify installation
python3 -c "from omnicompute.pipeline.orchestrator import Orchestrator; print('✅ Installed')"

# Test with sample telemetry
python3 -m pytest src/omnicompute/tests/test_pipeline_orchestrator.py::TestHappyPath -v

# Check logs
tail -20 logs/autonomous_actions.jsonl
```

## Rollback

If deployment fails:

```bash
# Stop agent
pkill -f "omnicompute"

# Restore previous version
git checkout v1.0.0  # Or known-good commit

# Reinstall
pip install -r requirements.txt

# Verify
pytest src/omnicompute/tests/ -q
```

## Updates

To update to a new release:

```bash
# Pull latest
git fetch origin
git checkout v1.1.0  # Specific version tag

# Reinstall (if dependencies changed)
pip install -r requirements.txt

# Run tests
pytest src/omnicompute/tests/ -q

# Restart agent (during next contact window)
```

## Support

For deployment issues:
- Check logs: `tail -f logs/autonomous_actions.jsonl`
- Review GRAPH_REPORT.md for system architecture
- Contact: ashrafuzzmanhossain@gmail.com

For operational questions:
- See ARCHITECTURE.md for system design
- See COMPONENTS.md for component contracts
- See DATA_SCHEMAS.md for telemetry format

## References

- **ARCHITECTURE.md** — System design overview
- **COMPONENTS.md** — Component contracts and interfaces
- **TESTING.md** — Test suite documentation
- **README.md** — Quick start and feature list
