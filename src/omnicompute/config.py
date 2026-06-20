"""Global configuration and constants for OmniCompute."""

# Power constraints
POWER_BUDGET_PERCENT_MAX = 5.0  # Maximum % of node power budget for autonomous actions

# Latency and size constraints
UPLINK_BUNDLE_SIZE_MAX_BYTES = 512 * 1024  # 512 KB max uplink bundle
CONTACT_WINDOW_MINUTES_MIN = 8  # Minimum contact window for satellites

# Anomaly thresholds
ANOMALY_Z_SCORE_WARNING = 2.0  # Warning threshold: |z-score| > 2.0
ANOMALY_Z_SCORE_CRITICAL = 3.0  # Critical threshold: |z-score| > 3.0

# Confidence thresholds
CONFIDENCE_AUTONOMOUS_ACTION_MIN = 0.75  # Minimum confidence for autonomous execution
CONFIDENCE_HITL_ESCALATION_MIN = 0.75  # Actions below this → HITL review

# Baseline requirements
BASELINE_AGE_DAYS_MIN_COMPLETE = 7  # Minimum days for "complete" baseline
BASELINE_DAYS_ROLLING = 30  # Rolling window for baseline calculation

# HITL queue
HITL_TIMEOUT_HOURS = 3  # Hours before HITL decision times out (2 orbits)
HITL_QUEUE_CAPACITY_MAX = 100  # Maximum items in queue before trimming

# Encryption
ENCRYPTION_ALGORITHM = "AES-256-GCM"  # FIPS-140-2 compliant

# Logging
LOG_AUTONOMOUS_ACTIONS_PATH = "logs/autonomous_actions.jsonl"

# Data paths
CONFIG_NODES_PATH = "config/nodes.yaml"
CONFIG_BASELINES_PATH = "config/baselines.json"
CONFIG_PLAYBOOKS_DIR = "config/playbooks/"

TELEMETRY_BATCH_PATH = "data/telemetry_batch_latest.json"
QUEUE_HITL_PATH = "queue/hitl_review.json"
OUTPUT_UPLINK_PATH_TEMPLATE = "output/uplink_bundle_{timestamp}.json"
