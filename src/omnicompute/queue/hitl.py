"""HumanReviewQueue: Manage human-in-the-loop escalation queue."""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Literal

from omnicompute.response.schemas import Action
from omnicompute.queue.schemas import QueueItem
from omnicompute.errors import QueueError
from omnicompute.config import HITL_TIMEOUT_HOURS, CONFIDENCE_HITL_ESCALATION_MIN

logger = logging.getLogger(__name__)


class HumanReviewQueue:
    """
    Manage HITL escalation queue for low-confidence and irreversible actions.

    Persists to /queue/hitl_review.json (append-only).
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
        evidence: List[str],
        timeout_hours: Optional[int] = None
    ) -> QueueItem:
        """
        Enqueue an action for HITL review.

        Args:
            action: Action to escalate
            evidence: List of supporting evidence strings
            timeout_hours: Hours until timeout (default: HITL_TIMEOUT_HOURS)

        Returns:
            QueueItem created and added to queue
        """
        timeout_hours = timeout_hours or HITL_TIMEOUT_HOURS
        now = datetime.now(timezone.utc)
        timeout_utc = now + timedelta(hours=timeout_hours)

        # Determine timeout action based on reversibility
        if action.reversible:
            timeout_action = "escalate_to_critical"
        else:
            timeout_action = "execute_with_log_entry_timeout_fallback"

        item = QueueItem(
            action_id=f"{action.node_id}_{action.action_type}_{now.timestamp()}",
            recommended_action=action.action_type,
            action_params=action.action_params,
            risk_level=self._assess_risk_level(action),
            supporting_evidence=evidence,
            confidence=action.confidence,
            reversible=action.reversible,
            queued_at_utc=now,
            timeout_utc=timeout_utc,
            timeout_action=timeout_action,
            status="pending",
            ground_response=None,
        )

        self._items.append(item)
        self._persist_queue()

        return item

    def check_timeouts(self, now: Optional[datetime] = None) -> List[QueueItem]:
        """
        Check for expired HITL items and escalate/execute as needed.

        Args:
            now: Current time (default: now in UTC)

        Returns:
            List of items that timed out (for logging/monitoring)
        """
        now = now or datetime.now(timezone.utc)
        timed_out = []

        for item in self._items:
            if item.status != "pending":
                continue

            if now > item.timeout_utc:
                timed_out.append(item)

                if item.timeout_action == "execute_with_log_entry_timeout_fallback":
                    # Irreversible action: execute with timeout log
                    item.status = "executed_timeout_fallback"
                    logger.warning(
                        f"HITL timeout: executing irreversible action {item.action_id} "
                        f"(confidence {item.confidence:.2f})"
                    )
                elif item.timeout_action == "escalate_to_critical":
                    # Low-confidence action: escalate to CRITICAL for next orbit
                    item.status = "escalated_critical"
                    logger.warning(
                        f"HITL timeout: escalating low-confidence action {item.action_id} "
                        f"to CRITICAL (confidence {item.confidence:.2f})"
                    )

        if timed_out:
            self._persist_queue()

        return timed_out

    def apply_ground_response(
        self,
        action_id: str,
        response: Literal["approved", "rejected"],
        notes: Optional[str] = None
    ) -> Optional[QueueItem]:
        """
        Apply ground response to a queued action.

        Args:
            action_id: ID of action in queue
            response: "approved" or "rejected"
            notes: Optional notes from ground

        Returns:
            QueueItem if found, None otherwise
        """
        for item in self._items:
            if item.action_id == action_id:
                item.ground_response = response
                item.status = response  # "approved" or "rejected"
                if notes:
                    item.supporting_evidence.append(f"Ground note: {notes}")

                self._persist_queue()
                logger.info(f"Ground response for {action_id}: {response}")
                return item

        logger.warning(f"Ground response for unknown action_id: {action_id}")
        return None

    def get_pending_items(self) -> List[QueueItem]:
        """Get all pending queue items."""
        return [item for item in self._items if item.status == "pending"]

    def _assess_risk_level(self, action: Action) -> str:
        """Assess risk level (critical, high, medium, low) of action."""
        if not action.reversible:
            if action.confidence < 0.5:
                return "critical"
            else:
                return "high"
        elif action.confidence < CONFIDENCE_HITL_ESCALATION_MIN:
            return "medium"
        else:
            return "low"

    def _load_queue(self) -> List[QueueItem]:
        """Load persisted queue from JSON."""
        if not self._queue_path.exists():
            return []

        try:
            data = json.loads(self._queue_path.read_text())
            items = []
            for item_dict in data.get("items", []):
                item = QueueItem(**item_dict)
                items.append(item)
            return items
        except Exception as e:
            logger.error(f"Failed to load queue from {self._queue_path}: {e}")
            return []

    def _persist_queue(self) -> None:
        """Persist queue to JSON (append-only)."""
        self._queue_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "items": [item.model_dump() for item in self._items]
        }

        try:
            self._queue_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to persist queue to {self._queue_path}: {e}")
            raise QueueError(f"Queue persistence failed: {e}")
