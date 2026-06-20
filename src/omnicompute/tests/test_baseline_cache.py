"""Test suite for BaselineCache (TDD - tests written before implementation).

Target component: src/omnicompute/anomaly/baseline.py

Contract under test:
    BaselineCache(data: dict | None = None)
        - Loads 30-day rolling baseline statistics, shaped like
          `/config/baselines.json`:
              {
                  "last_updated_utc": "<iso8601>",
                  "nodes": {
                      "<node_id>": {
                          "<metric_name>": {
                              "mean": float,
                              "stddev": float,
                              "days_samples": int
                          },
                          ...
                      },
                      ...
                  }
              }

    BaselineCache.get(node_id: str, metric_name: str) -> dict | None
        - Returns the baseline stats dict {"mean", "stddev", "days_samples"}
          for the given node + metric.
        - Returns None (never raises) when the node is unknown or the
          metric is missing for that node — graceful degradation.

    BaselineCache.z_score(value: float, baseline: dict) -> float
        - Computes (value - baseline["mean"]) / baseline["stddev"].
        - When stddev == 0 (no variance in 30-day window), the
          implementation returns float("inf") (or float("-inf") when
          value < mean, 0.0 when value == mean) rather than raising
          ZeroDivisionError. This documents the "no-raise" contract;
          if the implementation instead chooses to raise BaselineError
          for the zero-stddev case, update these tests to match exactly
          one of those two behaviors (this suite asserts the float(inf)
          convention as the primary contract).

    BaselineCache.update(node_id: str, metrics: dict) -> None
        - Merges (does not replace) new per-metric baseline stats for a
          node into the existing cache. Existing metrics not present in
          the update are preserved. New metrics are added. Metrics
          present in both old and new data are overwritten by the new
          values.

No implementation code is included in this file. Tests define the
contract for the implementation to satisfy.
"""

import math

import pytest

from omnicompute.anomaly.baseline import BaselineCache


# ---------------------------------------------------------------------------
# 1. Load baseline
# ---------------------------------------------------------------------------


class TestLoadBaseline:
    """Loading baseline data into the cache at construction time."""

    def test_load_valid_baseline_all_nodes_available(self, baseline_normal):
        """All nodes/metrics present in the source dict are retrievable."""
        cache = BaselineCache(baseline_normal)

        battery = cache.get("Sat-01", "battery_soc_percent")
        thermal = cache.get("Sat-01", "thermal_temp_celsius")

        assert battery is not None
        assert thermal is not None

    def test_load_incomplete_baseline_missing_metric_returns_none(
        self, baseline_missing_metric
    ):
        """Loading a baseline missing some metrics is not an error; the
        cache loads successfully and `.get()` returns None only for the
        specific metrics that are absent.
        """
        cache = BaselineCache(baseline_missing_metric)

        present = cache.get("Sat-01", "battery_soc_percent")
        missing = cache.get("Sat-01", "thermal_temp_celsius")

        assert present is not None
        assert missing is None


# ---------------------------------------------------------------------------
# 2. Get baseline
# ---------------------------------------------------------------------------


class TestGetBaseline:
    """`.get(node_id, metric_name)` retrieval semantics."""

    def test_get_known_node_and_metric_returns_stats_dict(
        self, baseline_cache_normal
    ):
        """Returns a dict containing mean, stddev, and days_samples."""
        result = baseline_cache_normal.get("Sat-01", "battery_soc_percent")

        assert isinstance(result, dict)
        assert set(["mean", "stddev", "days_samples"]).issubset(result.keys())
        assert result["mean"] == pytest.approx(65.0)
        assert result["stddev"] == pytest.approx(8.0)
        assert result["days_samples"] == 30

    def test_get_unknown_node_returns_none(self, baseline_cache_normal):
        """Unknown node_id never raises; returns None."""
        result = baseline_cache_normal.get("nonexistent_node", "battery_soc_percent")

        assert result is None

    def test_get_unknown_metric_for_known_node_returns_none(
        self, baseline_cache_normal
    ):
        """Known node but metric not tracked in baseline returns None."""
        result = baseline_cache_normal.get("Sat-01", "nonexistent_metric")

        assert result is None


# ---------------------------------------------------------------------------
# 3. Z-score calculation
# ---------------------------------------------------------------------------


class TestZScoreCalculation:
    """`.z_score(value, baseline)` numeric contract."""

    def test_z_score_positive_deviation(self, baseline_cache_normal):
        """value=75, mean=65, stddev=5 -> z_score ~= 2.0."""
        baseline = {"mean": 65.0, "stddev": 5.0, "days_samples": 30}

        result = baseline_cache_normal.z_score(75.0, baseline)

        assert result == pytest.approx(2.0)

    def test_z_score_negative_deviation(self, baseline_cache_normal):
        """value=55, mean=65, stddev=5 -> z_score ~= -2.0."""
        baseline = {"mean": 65.0, "stddev": 5.0, "days_samples": 30}

        result = baseline_cache_normal.z_score(55.0, baseline)

        assert result == pytest.approx(-2.0)

    def test_z_score_zero_stddev_returns_signed_infinity(self, baseline_cache_normal):
        """Zero stddev (no variance) must not raise ZeroDivisionError.

        Contract: returns float("inf") when value > mean, float("-inf")
        when value < mean, and 0.0 when value == mean exactly.
        """
        baseline = {"mean": 65.0, "stddev": 0.0, "days_samples": 30}

        above = baseline_cache_normal.z_score(70.0, baseline)
        below = baseline_cache_normal.z_score(60.0, baseline)
        equal = baseline_cache_normal.z_score(65.0, baseline)

        assert above == math.inf
        assert below == -math.inf
        assert equal == 0.0

    def test_z_score_very_large_deviation_calculated_correctly(
        self, baseline_cache_normal
    ):
        """Value far from mean produces a correctly scaled large z-score."""
        baseline = {"mean": 65.0, "stddev": 5.0, "days_samples": 30}

        result = baseline_cache_normal.z_score(165.0, baseline)

        assert result == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Graceful degradation and freshness signaling."""

    def test_zero_stddev_baseline_handled_gracefully(
        self, baseline_cache_normal, baseline_zero_stddev
    ):
        """A baseline entry with zero stddev does not raise on z_score()."""
        cache = BaselineCache(baseline_zero_stddev)
        baseline = cache.get("Sat-01", "battery_soc_percent")

        result = cache.z_score(80.0, baseline)

        assert result == math.inf

    def test_missing_baseline_get_returns_none_gracefully(
        self, baseline_cache_empty
    ):
        """An empty cache (no baselines loaded) never raises; .get() is None."""
        result = baseline_cache_empty.get("Sat-01", "battery_soc_percent")

        assert result is None

    def test_stale_baseline_still_usable_but_reports_days_samples(
        self, baseline_stale
    ):
        """A baseline with < 7 days of history is still usable for z_score,
        but callers can inspect `days_samples` to assess freshness/staleness
        (e.g., against BASELINE_AGE_DAYS_MIN_COMPLETE = 7).
        """
        cache = BaselineCache(baseline_stale)
        baseline = cache.get("Sat-01", "battery_soc_percent")

        assert baseline is not None
        assert baseline["days_samples"] < 7

        result = cache.z_score(80.0, baseline)
        assert isinstance(result, float)
        assert math.isfinite(result)


# ---------------------------------------------------------------------------
# 5. Update baseline
# ---------------------------------------------------------------------------


class TestUpdateBaseline:
    """`.update(node_id, metrics)` merge semantics."""

    def test_update_replaces_existing_metric_values(self, baseline_cache_normal):
        """Updating a metric that already exists overwrites its stats."""
        baseline_cache_normal.update(
            "Sat-01",
            {"battery_soc_percent": {"mean": 70.0, "stddev": 9.0, "days_samples": 30}},
        )

        result = baseline_cache_normal.get("Sat-01", "battery_soc_percent")

        assert result["mean"] == pytest.approx(70.0)
        assert result["stddev"] == pytest.approx(9.0)

    def test_partial_update_adds_new_metric_and_preserves_old_ones(
        self, baseline_cache_normal
    ):
        """A partial update merges in new metrics without dropping
        metrics that were not part of the update payload.
        """
        existing_before = baseline_cache_normal.get("Sat-01", "thermal_temp_celsius")
        assert existing_before is not None  # sanity check on fixture

        baseline_cache_normal.update(
            "Sat-01",
            {"new_metric_xyz": {"mean": 1.0, "stddev": 0.5, "days_samples": 10}},
        )

        new_metric = baseline_cache_normal.get("Sat-01", "new_metric_xyz")
        existing_after = baseline_cache_normal.get("Sat-01", "thermal_temp_celsius")

        assert new_metric is not None
        assert new_metric["mean"] == pytest.approx(1.0)
        assert existing_after == existing_before
