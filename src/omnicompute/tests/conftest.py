"""Shared pytest fixtures for OmniCompute test suite.

Provides reusable sample telemetry batches (valid, malformed, edge-case),
baseline cache fixtures, anomaly triager fixtures, and node config
fixtures shared across the anomaly detection test suites.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from omnicompute.telemetry.parser import TelemetryParser
from omnicompute.telemetry.schemas import Telemetry
from omnicompute.anomaly.baseline import BaselineCache
from omnicompute.anomaly.schemas import Anomaly
from omnicompute.response.schemas import Action


@pytest.fixture
def parser() -> TelemetryParser:
    """Return a fresh TelemetryParser instance for each test."""
    return TelemetryParser()


@pytest.fixture
def mock_logger(mocker):
    """Provide a mock logger that can be injected into TelemetryParser.

    Use this when a test needs to assert on logger calls directly rather
    than relying on `caplog`. Returns a MagicMock standing in for a
    `logging.Logger` instance.
    """
    return mocker.MagicMock(spec=logging.Logger)


@pytest.fixture
def valid_batch_single_node() -> dict:
    """Minimal valid telemetry batch containing exactly one node reading."""
    return {
        "batch_id": "batch_2026-06-19T20-15-00Z",
        "batch_timestamp_utc": "2026-06-19T20:15:00Z",
        "node_readings": [
            {
                "node_id": "Sat-01",
                "timestamp": "2026-06-19T20:10:00Z",
                "received_at_utc": "2026-06-19T20:15:00Z",
                "metrics": {
                    "power_draw_watts": 9.2,
                    "battery_soc_percent": 14.2,
                    "thermal_temp_celsius": 42.1,
                    "rf_signal_strength_dbm": -75.3,
                },
            }
        ],
    }


@pytest.fixture
def valid_batch_multi_node() -> dict:
    """Valid telemetry batch containing 3+ distinct node readings."""
    return {
        "batch_id": "batch_2026-06-19T20-15-00Z",
        "batch_timestamp_utc": "2026-06-19T20:15:00Z",
        "node_readings": [
            {
                "node_id": "Sat-01",
                "timestamp": "2026-06-19T20:10:00Z",
                "received_at_utc": "2026-06-19T20:15:00Z",
                "metrics": {
                    "power_draw_watts": 9.2,
                    "battery_soc_percent": 14.2,
                    "thermal_temp_celsius": 42.1,
                    "rf_signal_strength_dbm": -75.3,
                },
            },
            {
                "node_id": "FGN-Alpha",
                "timestamp": "2026-06-19T20:10:05Z",
                "received_at_utc": "2026-06-19T20:15:05Z",
                "metrics": {
                    "compute_load_percent": 68.5,
                    "thermal_temp_celsius": 51.2,
                    "rf_signal_strength_dbm": -88.1,
                    "disk_usage_percent": 82.0,
                },
            },
            {
                "node_id": "MCH-Primary",
                "timestamp": "2026-06-19T20:10:10Z",
                "received_at_utc": "2026-06-19T20:15:10Z",
                "metrics": {
                    "compute_load_percent": 22.0,
                    "thermal_temp_celsius": 30.5,
                },
            },
        ],
    }


@pytest.fixture
def batch_missing_node_id() -> dict:
    """Malformed batch: one record is missing the required node_id field."""
    return {
        "batch_id": "batch_missing_node_id",
        "batch_timestamp_utc": "2026-06-19T20:15:00Z",
        "node_readings": [
            {
                # node_id intentionally omitted
                "timestamp": "2026-06-19T20:10:00Z",
                "received_at_utc": "2026-06-19T20:15:00Z",
                "metrics": {"battery_soc_percent": 50.0},
            },
            {
                "node_id": "Sat-01",
                "timestamp": "2026-06-19T20:10:00Z",
                "received_at_utc": "2026-06-19T20:15:00Z",
                "metrics": {"battery_soc_percent": 50.0},
            },
        ],
    }


@pytest.fixture
def batch_missing_timestamp() -> dict:
    """Malformed batch: one record is missing the required timestamp field."""
    return {
        "batch_id": "batch_missing_timestamp",
        "batch_timestamp_utc": "2026-06-19T20:15:00Z",
        "node_readings": [
            {
                "node_id": "Sat-01",
                # timestamp intentionally omitted, no batch-level fallback usable
                "received_at_utc": "2026-06-19T20:15:00Z",
                "metrics": {"battery_soc_percent": 50.0},
            }
        ],
    }


@pytest.fixture
def batch_invalid_json() -> str:
    """Raw string that is not valid JSON syntax."""
    return '{"batch_id": "broken", "node_readings": [ { "node_id": "Sat-01", '


@pytest.fixture
def batch_empty() -> dict:
    """Valid JSON object with an empty node_readings list."""
    return {
        "batch_id": "batch_empty",
        "batch_timestamp_utc": "2026-06-19T20:15:00Z",
        "node_readings": [],
    }


@pytest.fixture
def batch_empty_json_object() -> dict:
    """Edge case: a bare empty JSON object with no keys at all."""
    return {}


def to_json_str(batch: dict) -> str:
    """Helper: serialize a fixture dict to a JSON string for parser input."""
    return json.dumps(batch)


# ---------------------------------------------------------------------------
# Baseline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def baseline_normal() -> dict:
    """30-day baseline for Sat-01 (and FGN-Alpha), all metrics healthy.

    Shape mirrors /config/baselines.json: nodes -> metric -> {mean, stddev,
    days_samples}.
    """
    return {
        "last_updated_utc": "2026-06-19T21:50:00Z",
        "nodes": {
            "Sat-01": {
                "power_draw_watts": {"mean": 8.5, "stddev": 1.2, "days_samples": 28},
                "battery_soc_percent": {"mean": 65.0, "stddev": 8.0, "days_samples": 30},
                "thermal_temp_celsius": {"mean": 35.0, "stddev": 5.0, "days_samples": 30},
                "rf_signal_strength_dbm": {"mean": -75.0, "stddev": 8.5, "days_samples": 30},
            },
            "FGN-Alpha": {
                "compute_load_percent": {"mean": 35.0, "stddev": 15.0, "days_samples": 30},
                "thermal_temp_celsius": {"mean": 28.0, "stddev": 8.0, "days_samples": 30},
            },
        },
    }


@pytest.fixture
def baseline_stale() -> dict:
    """Baseline with only 2 days of data (below the 7-day completeness floor)."""
    return {
        "last_updated_utc": "2026-06-19T21:50:00Z",
        "nodes": {
            "Sat-01": {
                "battery_soc_percent": {"mean": 65.0, "stddev": 8.0, "days_samples": 2},
                "thermal_temp_celsius": {"mean": 35.0, "stddev": 5.0, "days_samples": 2},
            },
        },
    }


@pytest.fixture
def baseline_zero_stddev() -> dict:
    """Baseline with zero stddev (no variance observed in the 30-day window)."""
    return {
        "last_updated_utc": "2026-06-19T21:50:00Z",
        "nodes": {
            "Sat-01": {
                "battery_soc_percent": {"mean": 65.0, "stddev": 0.0, "days_samples": 30},
            },
        },
    }


@pytest.fixture
def baseline_missing_metric() -> dict:
    """Baseline incomplete: Sat-01 has battery_soc_percent but not thermal."""
    return {
        "last_updated_utc": "2026-06-19T21:50:00Z",
        "nodes": {
            "Sat-01": {
                "battery_soc_percent": {"mean": 65.0, "stddev": 8.0, "days_samples": 30},
            },
        },
    }


@pytest.fixture
def baseline_cache_normal(baseline_normal) -> BaselineCache:
    """BaselineCache pre-loaded with the healthy 30-day baseline."""
    return BaselineCache(baseline_normal)


@pytest.fixture
def baseline_cache_empty() -> BaselineCache:
    """Empty BaselineCache (no baselines loaded) for degradation testing."""
    return BaselineCache({})


# ---------------------------------------------------------------------------
# Telemetry fixtures (anomaly triager suite)
# ---------------------------------------------------------------------------


def _telemetry(node_id: str, metrics: dict) -> Telemetry:
    """Helper: build a Telemetry instance with fixed, deterministic timestamps."""
    return Telemetry(
        node_id=node_id,
        timestamp=datetime(2026, 6, 19, 20, 10, 0, tzinfo=timezone.utc),
        received_at=datetime(2026, 6, 19, 20, 15, 0, tzinfo=timezone.utc),
        metrics=metrics,
    )


@pytest.fixture
def telemetry_normal_values() -> list:
    """Telemetry with all metrics within nominal range (|z| <= 2.0 for Sat-01)."""
    return [
        _telemetry(
            "Sat-01",
            {
                "battery_soc_percent": 65.0,  # mean=65, stddev=8 -> z=0.0
                "thermal_temp_celsius": 37.0,  # mean=35, stddev=5 -> z=0.4
                "rf_signal_strength_dbm": -75.0,  # mean=-75, stddev=8.5 -> z=0.0
            },
        )
    ]


@pytest.fixture
def telemetry_critical_battery() -> list:
    """Telemetry with a CRITICAL battery anomaly (z-score > 3) for Sat-01.

    mean=65, stddev=8 -> value=14.2 yields z = (14.2 - 65) / 8 = -6.35.
    """
    return [
        _telemetry(
            "Sat-01",
            {
                "battery_soc_percent": 14.2,
            },
        )
    ]


@pytest.fixture
def telemetry_warning_thermal() -> list:
    """Telemetry with a WARNING thermal anomaly (2 < z-score <= 3) for Sat-01.

    mean=35, stddev=5 -> value=47.5 yields z = (47.5 - 35) / 5 = 2.5.
    """
    return [
        _telemetry(
            "Sat-01",
            {
                "thermal_temp_celsius": 47.5,
            },
        )
    ]


@pytest.fixture
def telemetry_outside_safe_range() -> list:
    """Telemetry with a value outside safe_ranges even though z-score is low.

    Sat-01 safe_ranges.thermal_temp_celsius = [0, 85]; value=90 is outside
    that range. mean=35, stddev=5 -> z = (90 - 35) / 5 = 11.0, which is also
    > 3.0, but this fixture exists to exercise the safe_ranges override path
    independent of z-score magnitude.
    """
    return [
        _telemetry(
            "Sat-01",
            {
                "thermal_temp_celsius": 90.0,
            },
        )
    ]


# ---------------------------------------------------------------------------
# Node config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def node_config_sat01() -> dict:
    """Config for Sat-01 with safe_ranges, mirroring /config/nodes.yaml."""
    return {
        "Sat-01": {
            "node_type": "leo_satellite",
            "contact_window_minutes": 8,
            "power_budget_watts": 15,
            "safe_ranges": {
                "battery_soc_percent": [20, 100],
                "thermal_temp_celsius": [0, 85],
                "rf_signal_strength_dbm": [-120, -30],
            },
        },
    }


@pytest.fixture
def node_config_missing_safe_ranges() -> dict:
    """Config without safe_ranges; triager must degrade to z-score only."""
    return {
        "Sat-01": {
            "node_type": "leo_satellite",
            "contact_window_minutes": 8,
            "power_budget_watts": 15,
        },
    }


# ---------------------------------------------------------------------------
# Triager fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triager_with_baseline(baseline_cache_normal, node_config_sat01):
    """AnomalyTriager with a populated baseline cache and node config."""
    from omnicompute.anomaly.triager import AnomalyTriager

    return AnomalyTriager(
        baseline_cache=baseline_cache_normal, node_config=node_config_sat01
    )


@pytest.fixture
def triager_no_baseline(baseline_cache_empty, node_config_sat01):
    """AnomalyTriager with an empty baseline cache (graceful degradation)."""
    from omnicompute.anomaly.triager import AnomalyTriager

    return AnomalyTriager(
        baseline_cache=baseline_cache_empty, node_config=node_config_sat01
    )


# ---------------------------------------------------------------------------
# Anomaly fixtures (response planner / HITL queue suites)
# ---------------------------------------------------------------------------


def _anomaly(
    node_id: str = "Sat-01",
    metric_name: str = "battery_soc_percent",
    current_value: float = 14.2,
    baseline_mean: float = 65.0,
    baseline_stddev: float = 8.0,
    z_score: float = -6.35,
    severity: str = "CRITICAL",
    confidence: float = 0.90,
    timestamp: datetime = None,
) -> Anomaly:
    """Helper: build an Anomaly with sensible CRITICAL-battery defaults."""
    return Anomaly(
        node_id=node_id,
        metric_name=metric_name,
        current_value=current_value,
        baseline_mean=baseline_mean,
        baseline_stddev=baseline_stddev,
        z_score=z_score,
        severity=severity,
        confidence=confidence,
        timestamp=timestamp or datetime(2026, 6, 19, 20, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def anomaly_critical_battery() -> Anomaly:
    """CRITICAL battery anomaly (z-score > 3) for Sat-01."""
    return _anomaly(
        metric_name="battery_soc_percent",
        current_value=14.2,
        baseline_mean=65.0,
        baseline_stddev=8.0,
        z_score=-6.35,
        severity="CRITICAL",
        confidence=0.90,
    )


@pytest.fixture
def anomaly_warning_thermal() -> Anomaly:
    """WARNING thermal anomaly (2 < z-score <= 3) for Sat-01."""
    return _anomaly(
        metric_name="thermal_temp_celsius",
        current_value=47.5,
        baseline_mean=35.0,
        baseline_stddev=5.0,
        z_score=2.5,
        severity="WARNING",
        confidence=0.75,
    )


@pytest.fixture
def anomaly_nominal_metric() -> Anomaly:
    """NOMINAL metric anomaly result (no action should be generated)."""
    return _anomaly(
        metric_name="rf_signal_strength_dbm",
        current_value=-75.0,
        baseline_mean=-75.0,
        baseline_stddev=8.5,
        z_score=0.0,
        severity="NOMINAL",
        confidence=0.60,
    )


@pytest.fixture
def anomaly_unknown_type() -> Anomaly:
    """Anomaly whose metric_name has no corresponding playbook (fallback path)."""
    return _anomaly(
        metric_name="micrometeorite_impact_count",
        current_value=3.0,
        baseline_mean=0.0,
        baseline_stddev=0.5,
        z_score=6.0,
        severity="CRITICAL",
        confidence=0.80,
    )


# ---------------------------------------------------------------------------
# Playbook fixtures (response planner suite)
# ---------------------------------------------------------------------------


@pytest.fixture
def playbook_power_anomaly_dict() -> dict:
    """Raw dict matching the expected power_anomaly.yaml schema."""
    return {
        "name": "power_anomaly",
        "anomaly_type": "battery_soc_percent",
        "triggers": [
            {"metric": "battery_soc_percent", "severity": "CRITICAL"},
        ],
        "actions": [
            {
                "action_type": "load_shed",
                "params": {"target_watts": 6.0, "exclude": []},
                "reversible": True,
                "reversibility_window_seconds": 1800,
                "estimated_impact": "reduce_power_draw_by_3w",
                "min_confidence": 0.6,
            },
            {
                "action_type": "reduce_beacon",
                "params": {"interval_seconds": 60},
                "reversible": True,
                "reversibility_window_seconds": 900,
                "estimated_impact": "reduce_power_draw_by_0.5w",
                "min_confidence": 0.6,
            },
        ],
        "modifiers": [
            {
                "when": "solar_degradation > 20",
                "effect": "exclude_action_param",
                "target_action": "load_shed",
                "exclude": "rf_backup",
            },
            {
                "when": "eclipse",
                "effect": "aggressive_load_shed",
            },
        ],
    }


@pytest.fixture
def playbook_thermal_violation_dict() -> dict:
    """Raw dict matching the expected thermal_violation.yaml schema."""
    return {
        "name": "thermal_violation",
        "anomaly_type": "thermal_temp_celsius",
        "triggers": [
            {"metric": "thermal_temp_celsius", "severity": "WARNING"},
            {"metric": "thermal_temp_celsius", "severity": "CRITICAL"},
        ],
        "actions": [
            {
                "action_type": "reduce_compute_load",
                "params": {"target_percent": 50},
                "reversible": True,
                "reversibility_window_seconds": 1200,
                "estimated_impact": "reduce_heat_generation",
                "min_confidence": 0.6,
            },
        ],
        "modifiers": [],
    }


@pytest.fixture
def playbook_rf_jamming_dict() -> dict:
    """Raw dict matching the expected rf_jamming.yaml schema (irreversible action)."""
    return {
        "name": "rf_jamming",
        "anomaly_type": "rf_signal_strength_dbm",
        "triggers": [
            {"metric": "rf_signal_strength_dbm", "severity": "CRITICAL"},
        ],
        "actions": [
            {
                "action_type": "switch_to_backup_antenna",
                "params": {},
                "reversible": False,
                "reversibility_window_seconds": None,
                "estimated_impact": "restore_rf_link",
                "min_confidence": 0.9,
            },
        ],
        "modifiers": [],
    }


@pytest.fixture
def playbooks_dir(tmp_path, playbook_power_anomaly_dict, playbook_thermal_violation_dict, playbook_rf_jamming_dict):
    """Directory on disk containing sample playbook YAML files.

    Mirrors the expected layout of /playbooks/*.yaml: one YAML file per
    anomaly type, loaded by ResponsePlanner at construction time.
    """
    directory = tmp_path / "playbooks"
    directory.mkdir()

    (directory / "power_anomaly.yaml").write_text(
        yaml.safe_dump(playbook_power_anomaly_dict)
    )
    (directory / "thermal_violation.yaml").write_text(
        yaml.safe_dump(playbook_thermal_violation_dict)
    )
    (directory / "rf_jamming.yaml").write_text(
        yaml.safe_dump(playbook_rf_jamming_dict)
    )

    return directory


@pytest.fixture
def playbooks_dir_with_malformed_file(playbooks_dir):
    """playbooks_dir plus one malformed YAML file that should be skipped/logged,
    not crash the loader.
    """
    malformed = playbooks_dir / "broken.yaml"
    malformed.write_text("name: broken\n  bad_indent: [unterminated")
    return playbooks_dir


@pytest.fixture
def playbooks_dir_empty(tmp_path):
    """Empty playbooks directory (no YAML files at all)."""
    directory = tmp_path / "playbooks_empty"
    directory.mkdir()
    return directory


# ---------------------------------------------------------------------------
# Action fixtures (response planner / HITL queue suites)
# ---------------------------------------------------------------------------


@pytest.fixture
def action_load_shed() -> Action:
    """Load shedding action: reversible, high confidence -> autonomous execution."""
    return Action(
        node_id="Sat-01",
        action_type="load_shed",
        params={"target_watts": 6.0},
        rationale="battery_soc_percent CRITICAL; shed load to extend runtime",
        reversible=True,
        reversibility_window_seconds=1800,
        estimated_impact="reduce_power_draw_by_3w",
        confidence=0.85,
        min_confidence_for_autonomous=0.75,
        source_anomaly_metric="battery_soc_percent",
        playbook_name="power_anomaly",
    )


@pytest.fixture
def action_irreversible_throttle() -> Action:
    """Compute throttle action: irreversible, low confidence -> HITL escalation."""
    return Action(
        node_id="Sat-01",
        action_type="compute_throttle",
        params={"target_percent": 40},
        rationale="thermal_temp_celsius CRITICAL; throttle compute to reduce heat",
        reversible=False,
        reversibility_window_seconds=None,
        estimated_impact="reduce_heat_generation",
        confidence=0.55,
        min_confidence_for_autonomous=0.75,
        source_anomaly_metric="thermal_temp_celsius",
        playbook_name="thermal_violation",
    )


@pytest.fixture
def action_reversible_low_confidence() -> Action:
    """Reversible action with confidence below the autonomous-execution floor."""
    return Action(
        node_id="Sat-01",
        action_type="reduce_beacon",
        params={"interval_seconds": 60},
        rationale="marginal signal; reduce beacon frequency as a precaution",
        reversible=True,
        reversibility_window_seconds=900,
        estimated_impact="reduce_power_draw_by_0.5w",
        confidence=0.5,
        min_confidence_for_autonomous=0.75,
        source_anomaly_metric="rf_signal_strength_dbm",
        playbook_name="rf_jamming",
    )


@pytest.fixture
def action_irreversible_high_confidence() -> Action:
    """Irreversible action with high confidence -> still escalated (reversible=False rule)."""
    return Action(
        node_id="Sat-01",
        action_type="switch_to_backup_antenna",
        params={},
        rationale="RF jamming detected; switch to backup antenna",
        reversible=False,
        reversibility_window_seconds=None,
        estimated_impact="restore_rf_link",
        confidence=0.95,
        min_confidence_for_autonomous=0.75,
        source_anomaly_metric="rf_signal_strength_dbm",
        playbook_name="rf_jamming",
    )


# ---------------------------------------------------------------------------
# Node config with power budget (response planner suite)
# ---------------------------------------------------------------------------


@pytest.fixture
def node_config_with_power_budget() -> dict:
    """Sat-01 config including power_budget_watts, for action budget checks."""
    return {
        "Sat-01": {
            "node_type": "leo_satellite",
            "contact_window_minutes": 8,
            "power_budget_watts": 15,
            "safe_ranges": {
                "battery_soc_percent": [20, 100],
                "thermal_temp_celsius": [0, 85],
                "rf_signal_strength_dbm": [-120, -30],
            },
        },
    }


@pytest.fixture
def node_config_no_power_budget() -> dict:
    """Sat-01 config without power_budget_watts (graceful degradation)."""
    return {
        "Sat-01": {
            "node_type": "leo_satellite",
            "contact_window_minutes": 8,
        },
    }


# ---------------------------------------------------------------------------
# ResponsePlanner fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def planner_with_playbooks(baseline_cache_normal, node_config_with_power_budget, playbooks_dir):
    """ResponsePlanner constructed with all sample playbooks loaded from disk."""
    from omnicompute.response.planner import ResponsePlanner

    return ResponsePlanner(
        baseline_cache=baseline_cache_normal,
        node_config=node_config_with_power_budget,
        playbooks_dir=str(playbooks_dir),
    )


@pytest.fixture
def planner_no_playbooks(baseline_cache_normal, node_config_with_power_budget, playbooks_dir_empty):
    """ResponsePlanner with no playbooks loaded (pure fallback mode)."""
    from omnicompute.response.planner import ResponsePlanner

    return ResponsePlanner(
        baseline_cache=baseline_cache_normal,
        node_config=node_config_with_power_budget,
        playbooks_dir=str(playbooks_dir_empty),
    )


@pytest.fixture
def planner_no_node_config(baseline_cache_normal, playbooks_dir):
    """ResponsePlanner with no node_config supplied (graceful degradation)."""
    from omnicompute.response.planner import ResponsePlanner

    return ResponsePlanner(
        baseline_cache=baseline_cache_normal,
        node_config=None,
        playbooks_dir=str(playbooks_dir),
    )


# ---------------------------------------------------------------------------
# HumanReviewQueue fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def hitl_queue_path(tmp_path):
    """Path to a fresh (non-existent) hitl_review.json for a clean queue."""
    return tmp_path / "queue" / "hitl_review.json"


@pytest.fixture
def queue_empty(hitl_queue_path):
    """Empty HumanReviewQueue backed by a fresh, non-existent JSON file."""
    from omnicompute.queue.hitl import HumanReviewQueue

    return HumanReviewQueue(queue_path=str(hitl_queue_path))


def _queue_item_kwargs(
    action_id: str = "act-0001",
    recommended_action: str = "compute_throttle",
    risk_level: str = "CRITICAL",
    confidence: float = 0.55,
    reversible: bool = False,
    queued_at_utc: datetime = None,
    timeout_utc: datetime = None,
    timeout_action: str = "escalate_to_critical",
    status: str = "PENDING",
) -> dict:
    """Helper: build kwargs for a QueueItem with deterministic timestamps."""
    queued_at = queued_at_utc or datetime(2026, 6, 19, 20, 10, 0, tzinfo=timezone.utc)
    timeout_at = timeout_utc or (queued_at + timedelta(hours=3))
    return dict(
        action_id=action_id,
        recommended_action=recommended_action,
        action_params={"target_percent": 40},
        risk_level=risk_level,
        supporting_evidence=[
            {
                "metric_name": "battery_soc_percent",
                "z_score": -6.35,
                "baseline_mean": 65.0,
            }
        ],
        confidence=confidence,
        reversible=reversible,
        queued_at_utc=queued_at,
        timeout_utc=timeout_at,
        timeout_action=timeout_action,
        status=status,
        ground_response=None,
    )


@pytest.fixture
def queue_item_pending_not_expired():
    """QueueItem whose timeout_utc is in the future relative to the fixed 'now'."""
    from omnicompute.queue.schemas import QueueItem

    now = datetime(2026, 6, 19, 21, 0, 0, tzinfo=timezone.utc)
    kwargs = _queue_item_kwargs(
        action_id="act-pending",
        queued_at_utc=now - timedelta(minutes=10),
        timeout_utc=now + timedelta(hours=2),
    )
    return QueueItem(**kwargs)


@pytest.fixture
def queue_item_expired_irreversible():
    """QueueItem past its timeout_utc, irreversible action -> execute_with_log."""
    from omnicompute.queue.schemas import QueueItem

    now = datetime(2026, 6, 19, 23, 30, 0, tzinfo=timezone.utc)
    kwargs = _queue_item_kwargs(
        action_id="act-expired-irreversible",
        reversible=False,
        timeout_action="execute_with_log",
        queued_at_utc=now - timedelta(hours=4),
        timeout_utc=now - timedelta(hours=1),
    )
    return QueueItem(**kwargs)


@pytest.fixture
def queue_item_expired_low_confidence():
    """QueueItem past its timeout_utc, low confidence -> escalate_to_critical."""
    from omnicompute.queue.schemas import QueueItem

    now = datetime(2026, 6, 19, 23, 30, 0, tzinfo=timezone.utc)
    kwargs = _queue_item_kwargs(
        action_id="act-expired-low-confidence",
        reversible=True,
        confidence=0.4,
        risk_level="WARNING",
        timeout_action="escalate_to_critical",
        queued_at_utc=now - timedelta(hours=4),
        timeout_utc=now - timedelta(hours=1),
    )
    return QueueItem(**kwargs)


@pytest.fixture
def queue_with_items(hitl_queue_path):
    """HumanReviewQueue pre-populated with 3 items of varying risk levels."""
    from omnicompute.queue.hitl import HumanReviewQueue
    from omnicompute.queue.schemas import QueueItem

    queue = HumanReviewQueue(queue_path=str(hitl_queue_path))

    items = [
        QueueItem(**_queue_item_kwargs(action_id="act-info", risk_level="INFO", confidence=0.6, reversible=True)),
        QueueItem(**_queue_item_kwargs(action_id="act-warning", risk_level="WARNING", confidence=0.5, reversible=True)),
        QueueItem(**_queue_item_kwargs(action_id="act-critical", risk_level="CRITICAL", confidence=0.55, reversible=False)),
    ]
    for item in items:
        queue._items.append(item)  # direct seed; persistence exercised separately

    return queue


# ---------------------------------------------------------------------------
# Phase 3: UplinkBundler and Pipeline fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def encryption_key() -> str:
    """Fernet encryption key for testing uplink bundles."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


@pytest.fixture
def queue_empty(tmp_path):
    """Empty HumanReviewQueue for testing."""
    from omnicompute.queue.hitl import HumanReviewQueue
    queue_path = tmp_path / "hitl_queue.json"
    return HumanReviewQueue(queue_path=str(queue_path))
