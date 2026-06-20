"""Shared pytest fixtures for OmniCompute test suite.

Provides reusable sample telemetry batches (valid, malformed, edge-case),
baseline cache fixtures, anomaly triager fixtures, and node config
fixtures shared across the anomaly detection test suites.
"""

import json
import logging
from datetime import datetime, timezone

import pytest

from omnicompute.telemetry.parser import TelemetryParser
from omnicompute.telemetry.schemas import Telemetry
from omnicompute.anomaly.baseline import BaselineCache


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
