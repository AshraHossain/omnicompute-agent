"""ResponsePlanner: Generate response actions based on anomalies and playbooks."""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional

from omnicompute.anomaly.schemas import Anomaly
from omnicompute.response.schemas import Action, PlaybookAction
from omnicompute.errors import PlaybookError, ResponsePlanError

logger = logging.getLogger(__name__)


class ResponsePlanner:
    """Generate response actions by matching anomalies to playbooks."""

    def __init__(
        self,
        playbooks_dir: Optional[str] = None,
        node_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize response planner.

        Args:
            playbooks_dir: Path to playbooks directory (default: config/playbooks/)
            node_config: Dict of node_id → {power_budget_watts, safe_ranges, ...}
        """
        self._playbooks_dir = Path(playbooks_dir or "config/playbooks/")
        self._node_config = node_config or {}
        self._playbooks = self._load_playbooks()

    def plan(self, anomalies: List[Anomaly]) -> List[Action]:
        """
        Generate response actions for detected anomalies.

        Args:
            anomalies: List of Anomaly objects from AnomalyTriager

        Returns:
            List of Action objects (may be empty if no anomalies or no matching playbooks)
        """
        actions = []

        for anomaly in anomalies:
            anomaly_actions = self._plan_anomaly(anomaly)
            actions.extend(anomaly_actions)

        return actions

    def _plan_anomaly(self, anomaly: Anomaly) -> List[Action]:
        """Plan actions for a single anomaly."""
        # Infer anomaly type from metric name (e.g., battery_soc → power_anomaly)
        anomaly_type = self._infer_anomaly_type(anomaly.metric_name)

        # Try to find matching playbook
        playbook = self._playbooks.get(anomaly_type)
        if not playbook:
            # Fallback: generic alert-ground action
            return [
                Action(
                    node_id=anomaly.node_id,
                    action_type="alert_ground",
                    action_params={"reason": f"Unknown anomaly type: {anomaly_type}"},
                    rationale=f"No playbook for {anomaly_type}; escalating to ground",
                    reversible=False,
                    reversibility_window_seconds=0,
                    estimated_impact="Ground acknowledgment required",
                    confidence=anomaly.confidence,
                    min_confidence_for_autonomous=0.75
                )
            ]

        # Check trigger conditions
        triggered = self._check_triggers(playbook, anomaly)
        if not triggered:
            return []

        # Generate actions from playbook
        actions = []
        for pb_action in playbook.get("actions", []):
            action = Action(
                node_id=anomaly.node_id,
                action_type=pb_action["action"],
                action_params=pb_action.get("params", {}),
                rationale=pb_action.get("description", ""),
                reversible=pb_action.get("reversible", False),
                reversibility_window_seconds=pb_action.get("reversibility_window_seconds", 0),
                estimated_impact=pb_action.get("estimated_impact", ""),
                confidence=anomaly.confidence,  # Action inherits anomaly confidence
                min_confidence_for_autonomous=pb_action.get("min_confidence_for_autonomous", 0.75)
            )
            actions.append(action)

        return actions

    def _infer_anomaly_type(self, metric_name: str) -> str:
        """Infer anomaly type from metric name."""
        if "battery" in metric_name or "power" in metric_name:
            return "power_anomaly"
        elif "thermal" in metric_name or "temp" in metric_name:
            return "thermal_violation"
        elif "rf" in metric_name or "signal" in metric_name:
            return "rf_jamming"
        else:
            return "unknown"

    def _check_triggers(self, playbook: Dict[str, Any], anomaly: Anomaly) -> bool:
        """Check if anomaly matches playbook triggers."""
        triggers = playbook.get("triggers", [])
        if not triggers:
            return False

        for trigger in triggers:
            if self._check_trigger(trigger, anomaly):
                return True

        return False

    def _check_trigger(self, trigger: Dict[str, Any], anomaly: Anomaly) -> bool:
        """Check if anomaly matches a single trigger."""
        metric = trigger.get("metric")
        if metric != anomaly.metric_name:
            return False

        condition = trigger.get("condition", "")
        # Parse condition: "< 15", "> 3.0", etc.
        if "<" in condition:
            threshold = float(condition.replace("<", "").strip())
            return anomaly.current_value < threshold
        elif ">" in condition:
            threshold = float(condition.replace(">", "").strip())
            return anomaly.current_value > threshold
        elif "==" in condition:
            threshold = float(condition.replace("==", "").strip())
            return anomaly.current_value == threshold

        return False

    def _load_playbooks(self) -> Dict[str, Dict[str, Any]]:
        """Load all playbooks from directory."""
        playbooks = {}

        if not self._playbooks_dir.exists():
            logger.warning(f"Playbooks directory not found: {self._playbooks_dir}")
            return playbooks

        for yaml_file in self._playbooks_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    playbook = yaml.safe_load(f)
                    anomaly_type = playbook.get("anomaly_type", yaml_file.stem)
                    playbooks[anomaly_type] = playbook
                    logger.info(f"Loaded playbook: {anomaly_type}")
            except Exception as e:
                logger.error(f"Failed to load playbook {yaml_file}: {e}")

        return playbooks
