"""Pydantic data models for the Human-in-the-Loop (HITL) review queue."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class QueueItem(BaseModel):
    """A single HITL review queue entry.

    Created from an Action that failed autonomous-execution criteria
    (reversible is False, OR confidence < CONFIDENCE_HITL_ESCALATION_MIN).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action_id": "act-0001",
                "recommended_action": "compute_throttle",
                "action_params": {"target_percent": 40},
                "risk_level": "CRITICAL",
                "supporting_evidence": [
                    {
                        "metric_name": "battery_soc_percent",
                        "z_score": -6.35,
                        "baseline_mean": 65.0,
                    }
                ],
                "confidence": 0.55,
                "reversible": False,
                "queued_at_utc": "2026-06-19T20:10:00Z",
                "timeout_utc": "2026-06-19T23:10:00Z",
                "timeout_action": "escalate_to_critical",
                "status": "PENDING",
                "ground_response": None,
            }
        }
    )

    action_id: str = Field(..., description="Unique identifier for the originating action")
    recommended_action: str = Field(..., description="Action type recommended for review")
    action_params: Dict[str, Any] = Field(default_factory=dict)
    risk_level: Literal["INFO", "WARNING", "CRITICAL"] = Field(
        ..., description="Priority ranking used for queue trimming and uplink ordering"
    )
    supporting_evidence: List[Dict[str, Any]] = Field(
        default_factory=list, description="Evidence (metric, z-score, baseline) supporting escalation"
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reversible: bool = Field(..., description="Whether the underlying action is reversible")
    queued_at_utc: datetime = Field(..., description="When the action was proposed/queued")
    timeout_utc: datetime = Field(..., description="Deadline for ground response")
    timeout_action: Literal["execute_with_log", "escalate_to_critical"] = Field(
        ..., description="Fallback behavior if timeout expires with no ground response"
    )
    status: Literal[
        "PENDING", "APPROVED", "REJECTED", "EXECUTED", "ESCALATED", "EXPIRED"
    ] = Field("PENDING", description="Current lifecycle status of this queue item")
    ground_response: Optional[Literal["APPROVE", "REJECT"]] = Field(
        None, description="Ground operator decision, if received"
    )
