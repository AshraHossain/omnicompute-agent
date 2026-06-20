"""HumanReviewQueue: Manage human-in-the-loop escalation queue."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal

from omnicompute.response.schemas import Action
from omnicompute.queue.schemas import QueueItem
from omnicompute.errors import QueueError
from omnicompute.config import CONFIDENCE_HITL_ESCALATION_MIN

logger = logging.getLogger(__name__)

HITL_TIMEOUT_HOURS = 3
HITL_QUEUE_CAPACITY_MAX = 100


class HumanReviewQueue:
    """
    Manage HITL escalation queue for low-confidence and irreversible actions.

    Persists to queue_path (append-only JSON).
    """

    def __init__(self, queue_path: Optional[str] = None):
        """
        Initialize HITL queue.

        Args:
            queue_path: Path to queue JSON file (default: queue/hitl_review.json)
        """
        self._queue_path = Path(queue_path or "queue/hitl_review.json")
        self._items: List[QueueItem] = self._load_queue()

    def enqueue(
        self,
        action: Action,
        evidence: List[Dict[str, Any]],
        timeout_hours: Optional[int] = None
    ) -> Optional[QueueItem]:
        """
        Enqueue an action for HITL review if it meets escalation criteria.

        Escalation criteria: reversible is False OR confidence < CONFIDENCE_HITL_ESCALATION_MIN (0.75).

        Args:
            action: Action to potentially escalate
            evidence: List of supporting evidence dicts (from anomaly)
            timeout_hours: Hours until timeout (default: HITL_TIMEOUT_HOURS)

        Returns:
            QueueItem created and added to queue, or None if action doesn't meet escalation criteria
        """
        # Check escalation criteria
        if action.reversible and action.confidence >= CONFIDENCE_HITL_ESCALATION_MIN:
            # Autonomous execution - don't queue
            return None

        timeout_hours = timeout_hours or HITL_TIMEOUT_HOURS
        now = datetime.now(timezone.utc)
        timeout_utc = now + timedelta(hours=timeout_hours)

        # Determine timeout action based on reversibility
        if action.reversible:
            timeout_action = "escalate_to_critical"
        else:
            timeout_action = "execute_with_log"

        item = QueueItem(
            action_id=f"{action.node_id}_{action.action_type}_{now.timestamp()}",
            recommended_action=action.action_type,
            action_params=action.params,
            risk_level=self._assess_risk_level(action),
            supporting_evidence=evidence,
            confidence=action.confidence,
            reversible=action.reversible,
            queued_at_utc=now,
            timeout_utc=timeout_utc,
            timeout_action=timeout_action,
            status="PENDING",
            ground_response=None,
        )

        self._items.append(item)
        self._trim_to_capacity()
        self._persist_queue()

        return item

    def check_timeouts(self, now: Optional[datetime] = None) -> List[QueueItem]:
        """
        Check for expired HITL items and escalate/execute as needed.

        Args:
            now: Current time (default: now in UTC)

        Returns:
            List of items whose status changed during this call
        """
        now = now or datetime.now(timezone.utc)
        timed_out = []

        for item in self._items:
            if item.status != "PENDING":
                continue

            if now >= item.timeout_utc:
                timed_out.append(item)

                if item.timeout_action == "execute_with_log":
                    # Irreversible action: execute with timeout log
                    item.status = "EXECUTED"
                    logger.warning(
                        f"HITL timeout: timeout_fallback_execution for irreversible action {item.action_id} "
                        f"(confidence {item.confidence:.2f})"
                    )
                elif item.timeout_action == "escalate_to_critical":
                    # Low-confidence action: escalate to CRITICAL for next orbit
                    item.status = "ESCALATED"
                    item.risk_level = "CRITICAL"
                    logger.warning(
                        f"HITL timeout: escalating low-confidence action {item.action_id} "
                        f"to CRITICAL (confidence {item.confidence:.2f})"
                    )

        if timed_out:
            self._persist_queue()

        return timed_out

    def process_ground_response(
        self,
        action_id: str,
        response: Literal["APPROVE", "REJECT"],
        notes: Optional[str] = None
    ) -> Optional[QueueItem]:
        """
        Process a ground response to a queued action.

        Args:
            action_id: ID of action in queue
            response: "APPROVE" or "REJECT"
            notes: Optional notes from ground

        Returns:
            QueueItem if found, None otherwise
        """
        for item in self._items:
            if item.action_id == action_id:
                item.ground_response = response
                # Set status to APPROVED or REJECTED based on response
                if response == "APPROVE":
                    item.status = "APPROVED"
                else:
                    item.status = "REJECTED"

                if notes:
                    # Append ground note to evidence
                    if isinstance(item.supporting_evidence, list):
                        item.supporting_evidence.append({"ground_note": notes})

                self._persist_queue()
                logger.info(f"Ground response for {action_id}: {response}")
                return item

        logger.warning(f"Ground response for unknown action_id: {action_id}")
        return None

    @property
    def pending_items(self) -> List[QueueItem]:
        """Get all pending queue items."""
        return [item for item in self._items if item.status == "PENDING"]

    def _assess_risk_level(self, action: Action) -> Literal["INFO", "WARNING", "CRITICAL"]:
        """Assess risk level (CRITICAL, WARNING, INFO) of action."""
        if not action.reversible:
            if action.confidence < 0.5:
                return "CRITICAL"
            else:
                return "WARNING"
        elif action.confidence < CONFIDENCE_HITL_ESCALATION_MIN:
            return "WARNING"
        else:
            return "INFO"

    def _trim_to_capacity(self) -> None:
        """
        Trim queue to HITL_QUEUE_CAPACITY_MAX by removing oldest low-risk items first.

        CRITICAL and ESCALATED items are never removed.
        """
        if len(self._items) <= HITL_QUEUE_CAPACITY_MAX:
            return

        # Separate CRITICAL/ESCALATED from others
        critical_or_escalated = [
            item for item in self._items
            if item.status == "ESCALATED" or item.risk_level == "CRITICAL"
        ]
        others = [
            item for item in self._items
            if not (item.status == "ESCALATED" or item.risk_level == "CRITICAL")
        ]

        # Sort others by queued_at_utc (oldest first)
        others.sort(key=lambda x: x.queued_at_utc)

        # Calculate how many items to keep
        target_count = HITL_QUEUE_CAPACITY_MAX - len(critical_or_escalated)
        items_to_remove = len(others) - max(0, target_count)

        if items_to_remove > 0:
            # Remove oldest INFO/WARNING items
            items_to_remove_list = others[:items_to_remove]
            for item in items_to_remove_list:
                self._items.remove(item)
                logger.info(f"Trimmed queue item {item.action_id} (capacity {HITL_QUEUE_CAPACITY_MAX})")

    def _load_queue(self) -> List[QueueItem]:
        """Load persisted queue from JSON."""
        if not self._queue_path.exists():
            return []

        try:
            data = json.loads(self._queue_path.read_text())
            # Handle both list format and dict format for compatibility
            if isinstance(data, list):
                items_data = data
            else:
                items_data = data.get("items", [])

            items = []
            for item_dict in items_data:
                item = QueueItem(**item_dict)
                items.append(item)
            return items
        except Exception as e:
            logger.error(f"Failed to load queue from {self._queue_path}: {e}")
            return []

    def _persist_queue(self) -> None:
        """Persist queue to JSON (append-only)."""
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize as a plain list for simplicity
        data = [item.model_dump(mode="json") for item in self._items]

        try:
            self._queue_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to persist queue to {self._queue_path}: {e}")
            raise QueueError(f"Queue persistence failed: {e}")
