"""Pydantic data models for anomalies."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Anomaly(BaseModel):
    """Detected metric anomaly with severity and confidence."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "Sat-01",
                "metric_name": "battery_soc_percent",
                "current_value": 14.2,
                "baseline_mean": 65.0,
                "baseline_stddev": 8.0,
                "z_score": -2.8,
                "severity": "CRITICAL",
                "confidence": 0.82,
                "timestamp": "2026-06-19T20:10:00Z"
            }
        }
    )

    node_id: str = Field(..., description="Node where anomaly was detected")
    metric_name: str = Field(..., description="Name of the anomalous metric")
    current_value: float = Field(..., description="Current metric value")
    baseline_mean: float = Field(..., description="Baseline mean from 30-day history")
    baseline_stddev: float = Field(..., description="Baseline standard deviation")
    z_score: float = Field(..., description="Z-score: (current - mean) / stddev")
    severity: Literal["NOMINAL", "WARNING", "CRITICAL"] = Field(..., description="Severity level")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    timestamp: datetime = Field(..., description="UTC timestamp when anomaly was detected")
