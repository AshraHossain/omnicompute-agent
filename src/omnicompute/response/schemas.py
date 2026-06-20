"""Pydantic data models for response planning (Action, Playbook)."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Action(BaseModel):
    """A recommended or executed response action produced by ResponsePlanner.

    Reversible, high-confidence actions (confidence >= min_confidence_for_autonomous)
    may be executed autonomously. Irreversible or low-confidence actions are
    escalated to HumanReviewQueue.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_id": "Sat-01",
                "action_type": "load_shed",
                "params": {"target_watts": 6.0},
                "rationale": "battery_soc_percent CRITICAL z=-6.35; shed load to extend runtime",
                "reversible": True,
                "reversibility_window_seconds": 1800,
                "estimated_impact": "reduce_power_draw_by_3w",
                "confidence": 0.82,
                "min_confidence_for_autonomous": 0.75,
            }
        }
    )

    node_id: str = Field(..., description="Node this action targets")
    action_type: str = Field(..., description="Action identifier, e.g. load_shed, reduce_beacon")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action-specific parameters")
    rationale: str = Field(..., description="Human-readable justification for the action")
    reversible: bool = Field(..., description="Whether this action can be safely undone")
    reversibility_window_seconds: Optional[int] = Field(
        None, description="Time window in which the action can be reversed, if reversible"
    )
    estimated_impact: Optional[str] = Field(
        None, description="Short description of the expected effect of this action"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    min_confidence_for_autonomous: float = Field(
        0.75, ge=0.0, le=1.0, description="Minimum confidence required for autonomous execution"
    )
    source_anomaly_metric: Optional[str] = Field(
        None, description="Metric name of the triggering anomaly, if any"
    )
    playbook_name: Optional[str] = Field(
        None, description="Name of the playbook that generated this action, if any"
    )


class PlaybookTrigger(BaseModel):
    """A single trigger condition within a playbook."""

    metric: Optional[str] = Field(None, description="Metric name the trigger evaluates")
    severity: Optional[Literal["NOMINAL", "WARNING", "CRITICAL"]] = None
    min_z_score: Optional[float] = None
    max_z_score: Optional[float] = None


class PlaybookAction(BaseModel):
    """A single action template within a playbook."""

    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reversible: bool = True
    reversibility_window_seconds: Optional[int] = None
    estimated_impact: Optional[str] = None
    min_confidence: float = Field(0.75, ge=0.0, le=1.0)


class Playbook(BaseModel):
    """A condition-action playbook loaded from /playbooks/*.yaml."""

    name: str
    anomaly_type: str
    triggers: List[PlaybookTrigger] = Field(default_factory=list)
    actions: List[PlaybookAction] = Field(default_factory=list)
    modifiers: List[Dict[str, Any]] = Field(default_factory=list)
