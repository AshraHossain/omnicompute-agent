"""ResponsePlanner: Generate response actions based on anomalies and playbooks."""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional

from omnicompute.anomaly.schemas import Anomaly
from omnicompute.anomaly.baseline import BaselineCache
from omnicompute.response.schemas import Action
from omnicompute.errors import PlaybookError

logger = logging.getLogger(__name__)


class ResponsePlanner:
    """Generate response actions by matching anomalies to playbooks."""

    def __init__(
        self,
        baseline_cache: BaselineCache,
        node_config: Optional[Dict[str, Any]] = None,
        playbooks_dir: Optional[str] = None
    ):
        """
        Initialize response planner.

        Args:
            baseline_cache: BaselineCache instance for historical metrics
            node_config: Dict of node_id → {power_budget_watts, safe_ranges, ...}
            playbooks_dir: Path to playbooks directory (default: config/playbooks/)
        """
        self._baseline_cache = baseline_cache
        self._node_config = node_config or {}
        self._playbooks_dir = Path(playbooks_dir or "config/playbooks/")
        self._playbooks = self._load_playbooks()

    def plan(self, anomalies: List[Anomaly], context: Optional[Dict[str, Any]] = None) -> List[Action]:
        """
        Generate response actions for detected anomalies.

        Args:
            anomalies: List of Anomaly objects from AnomalyTriager
            context: Optional context dict for conditional modifiers (e.g. eclipse, solar_degradation)

        Returns:
            List of Action objects (may be empty if no anomalies or no matching playbooks)
        """
        if not anomalies:
            return []

        context = context or {}

        # Skip NOMINAL anomalies
        non_nominal = [a for a in anomalies if a.severity != "NOMINAL"]

        # Deduplicate: keep only unique (node_id, metric_name) combinations
        seen = set()
        deduplicated = []
        for anomaly in non_nominal:
            key = (anomaly.node_id, anomaly.metric_name)
            if key not in seen:
                seen.add(key)
                deduplicated.append(anomaly)

        actions = []
        for anomaly in deduplicated:
            anomaly_actions = self._plan_anomaly(anomaly, context)
            actions.extend(anomaly_actions)

        return actions

    def _plan_anomaly(self, anomaly: Anomaly, context: Optional[Dict[str, Any]] = None) -> List[Action]:
        """Plan actions for a single anomaly."""
        context = context or {}

        # Find playbook by anomaly_type (metric name)
        playbook = self._playbooks.get(anomaly.metric_name)

        if not playbook:
            # Fallback: generic alert-ground action
            return [
                Action(
                    node_id=anomaly.node_id,
                    action_type="alert_ground",
                    params={"reason": f"No playbook for metric: {anomaly.metric_name}"},
                    rationale=f"Unknown metric type; escalating to ground",
                    reversible=False,
                    reversibility_window_seconds=None,
                    estimated_impact="Ground acknowledgment required",
                    confidence=anomaly.confidence,
                    min_confidence_for_autonomous=0.75,
                    source_anomaly_metric=anomaly.metric_name,
                    playbook_name=None
                )
            ]

        # Check trigger conditions (match severity)
        triggered = self._check_triggers(playbook, anomaly)
        if not triggered:
            return []

        # Generate actions from playbook
        actions = []
        for pb_action in playbook.get("actions", []):
            # Action confidence = anomaly.confidence * playbook_action.min_confidence
            action_confidence = anomaly.confidence * pb_action.get("min_confidence", 0.75)
            action_confidence = max(0.0, min(1.0, action_confidence))  # Clamp to [0, 1]

            # Copy and potentially modify action params based on context/modifiers
            action_params = pb_action.get("params", {}).copy()
            action_type = pb_action["action_type"]
            action_params = self._apply_modifiers(action_params, action_type, playbook, context)

            action = Action(
                node_id=anomaly.node_id,
                action_type=pb_action["action_type"],
                params=action_params,
                rationale=f"{anomaly.metric_name} {anomaly.severity}; executing playbook action",
                reversible=pb_action.get("reversible", True),
                reversibility_window_seconds=pb_action.get("reversibility_window_seconds"),
                estimated_impact=pb_action.get("estimated_impact"),
                confidence=action_confidence,
                min_confidence_for_autonomous=pb_action.get("min_confidence", 0.75),
                source_anomaly_metric=anomaly.metric_name,
                playbook_name=playbook.get("name")
            )
            actions.append(action)

        return actions

    def _check_triggers(self, playbook: Dict[str, Any], anomaly: Anomaly) -> bool:
        """Check if anomaly matches playbook triggers."""
        triggers = playbook.get("triggers", [])
        if not triggers:
            return False

        for trigger in triggers:
            if self._check_trigger(trigger, anomaly):
                return True

        return False

    def _apply_modifiers(self, params: Dict[str, Any], action_type: str, playbook: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply conditional modifiers to action params based on context."""
        if not context:
            return params

        modifiers = playbook.get("modifiers", [])
        for modifier in modifiers:
            # Check if modifier applies to this action type
            target_action = modifier.get("target_action")
            if target_action and target_action != action_type:
                continue

            # Check if modifier's condition matches context
            when = modifier.get("when", "")
            if not self._modifier_condition_matches(when, context):
                continue

            effect = modifier.get("effect", "")
            if effect == "exclude_action_param":
                # Add to exclude list
                exclude_item = modifier.get("exclude")
                if exclude_item:
                    if "exclude" not in params:
                        params["exclude"] = []
                    if exclude_item not in params["exclude"]:
                        params["exclude"].append(exclude_item)

            elif effect == "aggressive_load_shed":
                # Increase target_watts for more aggressive load shedding
                if "target_watts" in params:
                    params["target_watts"] = params["target_watts"] * 1.5

        return params

    def _modifier_condition_matches(self, condition: str, context: Dict[str, Any]) -> bool:
        """Check if a modifier condition matches the given context."""
        if not condition:
            return False

        # Check "solar_degradation > 20" style conditions
        if "solar_degradation" in condition and ">" in condition:
            threshold = float(condition.split(">")[1].strip())
            solar_deg = context.get("solar_degradation", 0)
            return solar_deg > threshold

        # Check simple boolean conditions like "eclipse"
        if condition == "eclipse":
            return context.get("eclipse", False)

        return False

    def _check_trigger(self, trigger: Dict[str, Any], anomaly: Anomaly) -> bool:
        """Check if anomaly matches a single trigger."""
        # Check metric match
        metric = trigger.get("metric")
        if metric and metric != anomaly.metric_name:
            return False

        # Check severity match
        severity = trigger.get("severity")
        if severity and severity != anomaly.severity:
            return False

        # Check z-score bounds if specified
        min_z = trigger.get("min_z_score")
        max_z = trigger.get("max_z_score")

        if min_z is not None and anomaly.z_score < min_z:
            return False
        if max_z is not None and anomaly.z_score > max_z:
            return False

        return True

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
                    # Index by anomaly_type field (typically metric name)
                    anomaly_type = playbook.get("anomaly_type", yaml_file.stem)
                    playbooks[anomaly_type] = playbook
                    logger.info(f"Loaded playbook: {anomaly_type}")
            except Exception as e:
                # Log malformed files but don't crash
                logger.warning(f"Failed to load playbook {yaml_file}: {e}")

        return playbooks
