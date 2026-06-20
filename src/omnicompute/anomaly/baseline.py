"""BaselineCache: Manage 30-day rolling baseline statistics for metric anomaly detection."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaselineCache:
    """
    Cache for 30-day rolling baseline statistics (mean, stddev) per node+metric.

    Provides z-score calculation and graceful degradation for missing baselines.
    """

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        """
        Initialize baseline cache.

        Args:
            data: Dict with structure:
                  {
                      "nodes": {
                          "Sat-01": {
                              "battery_soc_percent": {"mean": 65.0, "stddev": 8.0, "days_samples": 30},
                              ...
                          },
                          ...
                      }
                  }
        """
        self._data = data or {}
        self._nodes = self._data.get("nodes", {})

    def get(self, node_id: str, metric_name: str) -> Optional[Dict[str, float]]:
        """
        Retrieve baseline statistics for a node+metric.

        Args:
            node_id: Node identifier (e.g., "Sat-01")
            metric_name: Metric name (e.g., "battery_soc_percent")

        Returns:
            Dict with {"mean": float, "stddev": float, "days_samples": int} or None if not found.
        """
        if node_id not in self._nodes:
            return None

        node_metrics = self._nodes.get(node_id, {})
        if metric_name not in node_metrics:
            return None

        return node_metrics[metric_name]

    def z_score(self, value: float, baseline: Dict[str, float]) -> float:
        """
        Calculate z-score for a metric value.

        Args:
            value: Current metric value
            baseline: Dict with {"mean": float, "stddev": float}

        Returns:
            Z-score: (value - mean) / stddev
            If stddev == 0, returns float('inf'), -float('inf'), or 0.0 depending on relationship to mean.
        """
        mean = baseline.get("mean", 0.0)
        stddev = baseline.get("stddev", 0.0)

        if stddev == 0.0:
            # No variance in baseline
            if value > mean:
                return float("inf")
            elif value < mean:
                return -float("inf")
            else:
                return 0.0

        return (value - mean) / stddev

    def update(self, node_id: str, metrics: Dict[str, Dict[str, float]]) -> None:
        """
        Update baseline cache for a node (merge semantics).

        Args:
            node_id: Node identifier
            metrics: Dict of metric_name → {"mean": float, "stddev": float, "days_samples": int}
        """
        if node_id not in self._nodes:
            self._nodes[node_id] = {}

        # Merge: new metrics override, old metrics preserved
        self._nodes[node_id].update(metrics)

    def load(self, data: Dict[str, Any]) -> None:
        """Load/replace baseline data."""
        self._data = data or {}
        self._nodes = self._data.get("nodes", {})
