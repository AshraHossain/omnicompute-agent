"""Pydantic data models for telemetry."""

from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Telemetry(BaseModel):
    """Normalized telemetry reading from a single node."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "Sat-01",
                "timestamp": "2026-06-19T20:10:00Z",
                "received_at": "2026-06-19T20:15:00Z",
                "metrics": {
                    "battery_soc_percent": 14.2,
                    "thermal_temp_celsius": 42.1,
                    "rf_signal_strength_dbm": -75.3
                }
            }
        }
    )

    node_id: str = Field(..., description="Unique node identifier (e.g., Sat-01, FGN-Alpha)")
    timestamp: datetime = Field(..., description="UTC timestamp when reading was taken")
    received_at: datetime = Field(..., description="UTC timestamp when reading was received")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Metric name → value mapping")

    @field_validator("timestamp", "received_at", mode="before")
    @classmethod
    def normalize_timestamps_to_utc(cls, v: Any) -> datetime:
        """Normalize all timestamps to UTC-aware datetime objects."""
        if isinstance(v, datetime):
            # If naive (no timezone), assume UTC. If aware, keep as-is.
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            # If already aware, return as-is (datetime comparison handles the same instant)
            return v
        return v

    @field_validator("metrics", mode="before")
    @classmethod
    def coerce_metrics_to_float(cls, v: Dict[str, Any]) -> Dict[str, float]:
        """Coerce all metric values to float; use 0.0 for non-numeric."""
        if not isinstance(v, dict):
            return {}
        result = {}
        for key, val in v.items():
            try:
                result[key] = float(val)
            except (TypeError, ValueError):
                result[key] = 0.0
        return result
