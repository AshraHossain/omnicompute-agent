"""Test suite for AnomalyTriager (TDD - tests written before implementation).

Target component: src/omnicompute/anomaly/triager.py

Contract under test:
    AnomalyTriager(baseline_cache: BaselineCache, node_config: dict | None = None)

    AnomalyTriager.triage(telemetry: list[Telemetry]) -> list[Anomaly]
        - Consumes a list of normalized Telemetry objects.
        - For each (node_id, metric_name, value) triple:
            1. Look up baseline via BaselineCache.get(node_id, metric_name).
            2. If baseline is available, compute z_score via
               BaselineCache.z_score(value, baseline).
            3. Look up safe_ranges for the metric via node_config
               (node_config[node_id]["safe_ranges"][metric_name] ->
               [min, max]), if node_config / safe_ranges are present.
            4. Assign severity:
                 - CRITICAL: |z_score| > 3.0, OR value outside safe_ranges
                   (safe_ranges always overrides/forces CRITICAL regardless
                   of z-score, when present and violated).
                 - WARNING: 2.0 < |z_score| <= 3.0 (and within safe_ranges,
                   or no safe_ranges defined).
                 - NOMINAL: |z_score| <= 2.0 (and within safe_ranges, or no
                   safe_ranges defined).
               When no baseline is available for a metric, severity falls
               back to safe_ranges-only evaluation (CRITICAL if violated,
               otherwise NOMINAL) since z-score cannot be computed.
            5. Assign confidence (0.0-1.0):
                 - Base confidence derives from z-score magnitude/certainty.
                 - Stale baseline (days_samples < BASELINE_AGE_DAYS_MIN_COMPLETE,
                   i.e. < 7) penalizes confidence (e.g., -0.1 relative to a
                   complete baseline of the same z-score).
                 - Redundant indicators (>=2 metrics on the same node/telemetry
                   flagged as anomalous in the same triage pass) boost
                   confidence for those metrics (e.g., +0.1), capped at 1.0.
                 - No baseline available for a metric -> confidence is
                   "AMBIGUOUS", represented numerically in the 0.1-0.3 range.
        - Returns a list of Anomaly objects. Each Anomaly is emitted only
          for metrics that have a result to report (this suite documents
          and asserts the convention that NOMINAL metrics ARE included in
          the returned list — i.e., triage() reports on every metric in
          the input telemetry, not just non-nominal ones. If the
          implementation instead chooses to omit NOMINAL entries, the
          "All metrics NOMINAL" tests in section 7 should be the ones
          updated to match; the CRITICAL/WARNING assertions in sections 1-2
          remain valid either way since they assert presence, not absence.)
        - Never raises on missing baseline or missing node_config; degrades
          gracefully per the rules above.

No implementation code is included in this file. Tests define the
contract for the implementation to satisfy.
"""

import pytest

from omnicompute.anomaly.schemas import Anomaly
from omnicompute.anomaly.triager import AnomalyTriager
from omnicompute.anomaly.baseline import BaselineCache


# ---------------------------------------------------------------------------
# 1. Happy path: CRITICAL severity
# ---------------------------------------------------------------------------


class TestCriticalSeverity:
    """CRITICAL is assigned for |z| > 3.0 or safe_range violations."""

    def test_high_positive_z_score_is_critical(self, triager_with_baseline):
        """z-score > 3.0 (e.g., far above mean) -> CRITICAL."""
        from omnicompute.tests.conftest import _telemetry

        telemetry = [_telemetry("Sat-01", {"battery_soc_percent": 100.0})]
        # mean=65, stddev=8 -> z = (100-65)/8 = 4.375

        result = triager_with_baseline.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.severity == "CRITICAL"
        assert anomaly.z_score > 3.0

    def test_high_negative_z_score_is_critical(
        self, triager_with_baseline, telemetry_critical_battery
    ):
        """z-score < -3.0 -> CRITICAL. battery_soc_percent=14.2, mean=65,
        stddev=8 -> z = -6.35.
        """
        result = triager_with_baseline.triage(telemetry_critical_battery)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.severity == "CRITICAL"
        assert anomaly.z_score < -3.0

    def test_value_outside_safe_range_is_critical_even_with_low_z_score(
        self, triager_with_baseline, telemetry_outside_safe_range
    ):
        """A metric value outside safe_ranges is CRITICAL, overriding
        whatever the z-score would otherwise indicate.
        """
        result = triager_with_baseline.triage(telemetry_outside_safe_range)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "CRITICAL"


# ---------------------------------------------------------------------------
# 2. Happy path: WARNING severity
# ---------------------------------------------------------------------------


class TestWarningSeverity:
    """WARNING is assigned for 2.0 < |z| <= 3.0 within safe ranges."""

    def test_moderate_positive_z_score_is_warning(
        self, triager_with_baseline, telemetry_warning_thermal
    ):
        """thermal_temp_celsius=47.5, mean=35, stddev=5 -> z=2.5 -> WARNING."""
        result = triager_with_baseline.triage(telemetry_warning_thermal)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "WARNING"
        assert 2.0 < anomaly.z_score <= 3.0

    def test_moderate_negative_z_score_is_warning(self, triager_with_baseline):
        """value=25, mean=35, stddev=5 -> z=-2.0... use -2.5 to land squarely
        in WARNING band: value=22.5 -> z=(22.5-35)/5=-2.5.
        """
        from omnicompute.tests.conftest import _telemetry

        telemetry = [_telemetry("Sat-01", {"thermal_temp_celsius": 22.5})]

        result = triager_with_baseline.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "WARNING"
        assert -3.0 <= anomaly.z_score < -2.0


# ---------------------------------------------------------------------------
# 3. Happy path: NOMINAL severity
# ---------------------------------------------------------------------------


class TestNominalSeverity:
    """NOMINAL is assigned for |z| <= 2.0 within safe ranges."""

    def test_low_z_score_is_nominal(self, triager_with_baseline, telemetry_normal_values):
        """All metrics within 2 sigma of baseline -> NOMINAL."""
        result = triager_with_baseline.triage(telemetry_normal_values)

        assert all(a.severity == "NOMINAL" for a in result)
        assert all(abs(a.z_score) <= 2.0 for a in result)

    def test_within_safe_ranges_with_marginal_z_score_is_nominal(
        self, triager_with_baseline
    ):
        """Value within safe_ranges and |z| exactly at boundary (2.0) is NOMINAL."""
        from omnicompute.tests.conftest import _telemetry

        telemetry = [_telemetry("Sat-01", {"thermal_temp_celsius": 45.0})]
        # mean=35, stddev=5 -> z = (45-35)/5 = 2.0 (boundary, inclusive NOMINAL)

        result = triager_with_baseline.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "NOMINAL"


# ---------------------------------------------------------------------------
# 4. Confidence scoring
# ---------------------------------------------------------------------------


class TestConfidenceScoring:
    """Confidence reflects baseline completeness, z-score strength, and
    redundant indicator corroboration.
    """

    def test_complete_baseline_high_z_score_yields_high_confidence(
        self, triager_with_baseline, telemetry_critical_battery
    ):
        """A complete (>=7 day) baseline plus a strong z-score signal
        should produce confidence >= 0.85.
        """
        result = triager_with_baseline.triage(telemetry_critical_battery)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.confidence >= 0.85

    def test_stale_baseline_penalizes_confidence(
        self, baseline_stale, node_config_sat01
    ):
        """A baseline with days_samples < 7 should yield lower confidence
        than an equivalent reading against a complete baseline.
        """
        from omnicompute.tests.conftest import _telemetry

        stale_cache = BaselineCache(baseline_stale)
        triager = AnomalyTriager(baseline_cache=stale_cache, node_config=node_config_sat01)

        telemetry = [_telemetry("Sat-01", {"battery_soc_percent": 14.2})]
        result = triager.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        # Same z-score magnitude as the complete-baseline CRITICAL case, but
        # confidence must be measurably lower due to staleness.
        assert anomaly.confidence < 0.85

    def test_redundant_indicators_boost_confidence(self, triager_with_baseline):
        """When multiple metrics on the same node are simultaneously
        anomalous (corroborating signals), confidence for each is boosted
        relative to a single isolated anomaly.
        """
        from omnicompute.tests.conftest import _telemetry

        single_anomaly = [_telemetry("Sat-01", {"battery_soc_percent": 14.2})]
        multi_anomaly = [
            _telemetry(
                "Sat-01",
                {
                    "battery_soc_percent": 14.2,
                    "thermal_temp_celsius": 90.0,
                    "rf_signal_strength_dbm": -119.0,
                },
            )
        ]

        single_result = triager_with_baseline.triage(single_anomaly)
        multi_result = triager_with_baseline.triage(multi_anomaly)

        single_confidence = next(
            a for a in single_result if a.metric_name == "battery_soc_percent"
        ).confidence
        multi_confidence = next(
            a for a in multi_result if a.metric_name == "battery_soc_percent"
        ).confidence

        assert multi_confidence >= single_confidence

    def test_no_baseline_yields_ambiguous_confidence(
        self, triager_no_baseline, telemetry_critical_battery
    ):
        """No baseline available for the metric -> confidence in the
        AMBIGUOUS range (0.1-0.3).
        """
        result = triager_no_baseline.triage(telemetry_critical_battery)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert 0.1 <= anomaly.confidence <= 0.3


# ---------------------------------------------------------------------------
# 5. Safe ranges integration
# ---------------------------------------------------------------------------


class TestSafeRangesIntegration:
    """Interaction between node_config safe_ranges and z-score severity."""

    def test_outside_safe_range_always_critical_overriding_z_score(
        self, triager_with_baseline
    ):
        """Even a moderate z-score becomes CRITICAL once safe_ranges is
        violated.
        """
        from omnicompute.tests.conftest import _telemetry

        # battery_soc_percent safe range = [20, 100]; value=10 violates it.
        # mean=65, stddev=8 -> z = (10-65)/8 = -6.875 (already > 3 too, but
        # the point under test is that safe_ranges is authoritative).
        telemetry = [_telemetry("Sat-01", {"battery_soc_percent": 10.0})]

        result = triager_with_baseline.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.severity == "CRITICAL"

    def test_within_safe_range_defers_to_z_score_severity(
        self, triager_with_baseline, telemetry_warning_thermal
    ):
        """A value inside safe_ranges does not force NOMINAL; the z-score
        severity (WARNING here) still applies.
        """
        result = triager_with_baseline.triage(telemetry_warning_thermal)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        # thermal_temp_celsius=47.5 is within Sat-01 safe_range [0, 85]
        assert anomaly.severity == "WARNING"

    def test_missing_safe_range_for_metric_uses_z_score_only(
        self, baseline_cache_normal, node_config_sat01
    ):
        """A metric without a defined safe_range falls back to z-score-only
        evaluation (e.g., power_draw_watts has no safe_range entry in the
        fixture config).
        """
        from omnicompute.tests.conftest import _telemetry

        triager = AnomalyTriager(
            baseline_cache=baseline_cache_normal, node_config=node_config_sat01
        )
        # mean=8.5, stddev=1.2 -> value=10.0 -> z=(10-8.5)/1.2=1.25 -> NOMINAL
        telemetry = [_telemetry("Sat-01", {"power_draw_watts": 10.0})]

        result = triager.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "power_draw_watts")

        assert anomaly.severity == "NOMINAL"


# ---------------------------------------------------------------------------
# 6. Baseline cache interaction
# ---------------------------------------------------------------------------


class TestBaselineCacheInteraction:
    """How the triager consults BaselineCache for each metric."""

    def test_uses_baseline_when_available(
        self, triager_with_baseline, telemetry_normal_values
    ):
        """When a baseline exists, baseline_mean/baseline_stddev on the
        resulting Anomaly reflect the cached values.
        """
        result = triager_with_baseline.triage(telemetry_normal_values)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.baseline_mean == pytest.approx(65.0)
        assert anomaly.baseline_stddev == pytest.approx(8.0)

    def test_missing_baseline_for_metric_marks_ambiguous_and_continues(
        self, triager_no_baseline, telemetry_normal_values
    ):
        """Missing baseline does not raise; triage continues and marks
        confidence AMBIGUOUS for the affected metric.
        """
        result = triager_no_baseline.triage(telemetry_normal_values)

        assert len(result) == len(telemetry_normal_values[0].metrics)
        assert all(0.1 <= a.confidence <= 0.3 for a in result)

    def test_zero_stddev_baseline_handled_gracefully(
        self, baseline_zero_stddev, node_config_sat01
    ):
        """A baseline with zero stddev does not raise; triage() still
        returns a result (z_score likely +/-inf or a sentinel, severity
        CRITICAL due to extreme deviation).
        """
        from omnicompute.tests.conftest import _telemetry

        cache = BaselineCache(baseline_zero_stddev)
        triager = AnomalyTriager(baseline_cache=cache, node_config=node_config_sat01)

        telemetry = [_telemetry("Sat-01", {"battery_soc_percent": 80.0})]

        result = triager.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "battery_soc_percent")

        assert anomaly.severity == "CRITICAL"


# ---------------------------------------------------------------------------
# 7. No anomalies
# ---------------------------------------------------------------------------


class TestNoAnomalies:
    """Boundary behavior for empty input and all-nominal input."""

    def test_empty_telemetry_list_returns_empty_anomaly_list(
        self, triager_with_baseline
    ):
        """No telemetry in -> no anomalies out."""
        result = triager_with_baseline.triage([])

        assert result == []

    def test_all_nominal_metrics_returns_results_all_marked_nominal(
        self, triager_with_baseline, telemetry_normal_values
    ):
        """Per the documented convention (see module docstring), triage()
        reports a result entry for every input metric. When every metric
        is within nominal bounds, the list is non-empty but every entry's
        severity is NOMINAL (none are WARNING/CRITICAL).
        """
        result = triager_with_baseline.triage(telemetry_normal_values)

        assert len(result) > 0
        assert all(a.severity == "NOMINAL" for a in result)


# ---------------------------------------------------------------------------
# 8. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Single metric, many metrics, missing node baseline, stale baseline."""

    def test_single_metric_telemetry_is_correctly_triaged(
        self, triager_with_baseline
    ):
        """A Telemetry object with exactly one metric produces exactly one
        Anomaly result.
        """
        from omnicompute.tests.conftest import _telemetry

        telemetry = [_telemetry("Sat-01", {"battery_soc_percent": 65.0})]

        result = triager_with_baseline.triage(telemetry)

        assert len(result) == 1
        assert isinstance(result[0], Anomaly)
        assert result[0].metric_name == "battery_soc_percent"

    def test_many_metrics_per_node_all_triaged(self, triager_with_baseline):
        """All metrics in a multi-metric telemetry reading are triaged,
        each producing its own Anomaly entry.
        """
        from omnicompute.tests.conftest import _telemetry

        telemetry = [
            _telemetry(
                "Sat-01",
                {
                    "power_draw_watts": 8.5,
                    "battery_soc_percent": 65.0,
                    "thermal_temp_celsius": 35.0,
                    "rf_signal_strength_dbm": -75.0,
                },
            )
        ]

        result = triager_with_baseline.triage(telemetry)

        assert len(result) == 4
        metric_names = {a.metric_name for a in result}
        assert metric_names == {
            "power_draw_watts",
            "battery_soc_percent",
            "thermal_temp_celsius",
            "rf_signal_strength_dbm",
        }

    def test_node_with_no_baseline_marks_all_metrics_ambiguous(
        self, triager_no_baseline
    ):
        """A node entirely absent from the baseline cache yields AMBIGUOUS
        confidence for every metric reported.
        """
        from omnicompute.tests.conftest import _telemetry

        telemetry = [
            _telemetry(
                "Sat-01",
                {"battery_soc_percent": 65.0, "thermal_temp_celsius": 35.0},
            )
        ]

        result = triager_no_baseline.triage(telemetry)

        assert len(result) == 2
        assert all(0.1 <= a.confidence <= 0.3 for a in result)

    def test_very_stale_baseline_yields_low_confidence_for_all_metrics(
        self, baseline_stale, node_config_sat01
    ):
        """A baseline with very few days_samples produces consistently
        low (penalized) confidence across all reported metrics.
        """
        from omnicompute.tests.conftest import _telemetry

        cache = BaselineCache(baseline_stale)
        triager = AnomalyTriager(baseline_cache=cache, node_config=node_config_sat01)

        telemetry = [
            _telemetry(
                "Sat-01",
                {"battery_soc_percent": 65.0, "thermal_temp_celsius": 35.0},
            )
        ]

        result = triager.triage(telemetry)

        assert len(result) == 2
        assert all(a.confidence < 0.85 for a in result)


# ---------------------------------------------------------------------------
# 9. Integration with node config
# ---------------------------------------------------------------------------


class TestNodeConfigIntegration:
    """How node_config (safe_ranges) is wired into severity assignment."""

    def test_node_config_with_safe_ranges_used_in_severity(
        self, triager_with_baseline, telemetry_outside_safe_range
    ):
        """When node_config provides safe_ranges, violations force CRITICAL."""
        result = triager_with_baseline.triage(telemetry_outside_safe_range)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "CRITICAL"

    def test_missing_node_config_degrades_gracefully_no_safe_range_check(
        self, baseline_cache_normal
    ):
        """No node_config at all (None) means no safe_ranges are available;
        severity must fall back to z-score-only evaluation without raising.
        """
        from omnicompute.tests.conftest import _telemetry

        triager = AnomalyTriager(baseline_cache=baseline_cache_normal, node_config=None)

        # thermal_temp_celsius=90 would violate Sat-01's safe_range [0, 85]
        # if config were present, but with no config it's z-score-only:
        # mean=35, stddev=5 -> z=(90-35)/5=11.0 -> still CRITICAL via z-score.
        telemetry = [_telemetry("Sat-01", {"thermal_temp_celsius": 90.0})]

        result = triager.triage(telemetry)
        anomaly = next(a for a in result if a.metric_name == "thermal_temp_celsius")

        assert anomaly.severity == "CRITICAL"
        assert anomaly.z_score > 3.0
