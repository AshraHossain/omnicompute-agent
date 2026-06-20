"""AnomalyTriager: Detect metric anomalies using z-score and safe range checks."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Literal

from omnicompute.telemetry.schemas import Telemetry
from omnicompute.anomaly.schemas import Anomaly
from omnicompute.anomaly.baseline import BaselineCache
from omnicompute.config import ANOMALY_Z_SCORE_WARNING, ANOMALY_Z_SCORE_CRITICAL

logger = logging.getLogger(__name__)


class AnomalyTriager:
    """
    Detect metric anomalies using z-score analysis and safe range validation.

    Consumes normalized Telemetry, compares against baseline, assigns severity/confidence.
    """

    def __init__(
        self,
        baseline_cache: Optional[BaselineCache] = None,
        node_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize anomaly triager.

        Args:
            baseline_cache: BaselineCache instance with historical statistics
            node_config: Dict of node_id → {safe_ranges: {metric: [min, max]}, ...}
        """
        self._baseline = baseline_cache or BaselineCache()
        self._node_config = node_config or {}

    def triage(self, telemetry: List[Telemetry]) -> List[Anomaly]:
        """
        Triage telemetry records for anomalies.

        Args:
            telemetry: List of normalized Telemetry objects

        Returns:
            List of detected Anomaly objects (empty if no anomalies).
        """
        anomalies = []

        for t in telemetry:
            node_anomalies = self._triage_node(t)
            anomalies.extend(node_anomalies)

        return anomalies

    def _triage_node(self, telemetry: Telemetry) -> List[Anomaly]:
        """Triage a single node's telemetry reading."""
        anomalies = []

        for metric_name, value in telemetry.metrics.items():
            anomaly = self._triage_metric(
                node_id=telemetry.node_id,
                metric_name=metric_name,
                value=value,
                timestamp=telemetry.timestamp
            )
            if anomaly:
                anomalies.append(anomaly)

        return anomalies

    def _triage_metric(
        self,
        node_id: str,
        metric_name: str,
        value: float,
        timestamp: datetime
    ) -> Anomaly:
        """Triage a single metric. Always returns an Anomaly object (severity may be NOMINAL)."""

        # Step 1: Get baseline for this metric
        baseline = self._baseline.get(node_id, metric_name)
        if baseline is None:
            # No baseline; mark as AMBIGUOUS confidence
            return Anomaly(
                node_id=node_id,
                metric_name=metric_name,
                current_value=value,
                baseline_mean=0.0,
                baseline_stddev=0.0,
                z_score=0.0,
                severity="NOMINAL",
                confidence=0.1,  # AMBIGUOUS
                timestamp=timestamp
            )

        # Step 2: Calculate z-score
        z_score = self._baseline.z_score(value, baseline)

        # Step 3: Check safe ranges (if available)
        safe_ranges = self._get_safe_ranges(node_id, metric_name)
        outside_safe_range = safe_ranges and (
            value < safe_ranges[0] or value > safe_ranges[1]
        )

        # Step 4: Assign severity
        severity = self._assign_severity(z_score, outside_safe_range)

        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(z_score, baseline, severity)

        return Anomaly(
            node_id=node_id,
            metric_name=metric_name,
            current_value=value,
            baseline_mean=baseline["mean"],
            baseline_stddev=baseline["stddev"],
            z_score=z_score,
            severity=severity,
            confidence=confidence,
            timestamp=timestamp
        )

    def _assign_severity(
        self,
        z_score: float,
        outside_safe_range: bool
    ) -> Literal["NOMINAL", "WARNING", "CRITICAL"]:
        """Assign severity based on z-score and safe range."""
        # Safe range violation always → CRITICAL
        if outside_safe_range:
            return "CRITICAL"

        # Z-score-based severity
        if abs(z_score) > ANOMALY_Z_SCORE_CRITICAL:
            return "CRITICAL"
        elif abs(z_score) > ANOMALY_Z_SCORE_WARNING:
            return "WARNING"
        else:
            return "NOMINAL"

    def _calculate_confidence(
        self,
        z_score: float,
        baseline: Dict[str, float],
        severity: str
    ) -> float:
        """Calculate confidence score for anomaly detection."""
        # Base confidence: higher |z-score| → higher confidence
        abs_z = abs(z_score)

        if abs_z > ANOMALY_Z_SCORE_CRITICAL:
            base_confidence = 0.90
        elif abs_z > ANOMALY_Z_SCORE_WARNING:
            base_confidence = 0.75
        else:
            base_confidence = 0.60

        # Adjust for baseline age (days_samples)
        days_samples = baseline.get("days_samples", 0)
        if days_samples < 7:
            # Stale baseline: penalize confidence
            base_confidence -= 0.1

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, base_confidence))

    def _get_safe_ranges(self, node_id: str, metric_name: str) -> Optional[List[float]]:
        """Get safe range [min, max] for a metric, or None if not defined."""
        node = self._node_config.get(node_id)
        if not node:
            return None

        safe_ranges = node.get("safe_ranges", {})
        range_spec = safe_ranges.get(metric_name)

        if range_spec and isinstance(range_spec, (list, tuple)) and len(range_spec) == 2:
            return list(range_spec)

        return None
