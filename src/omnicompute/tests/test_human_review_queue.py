"""Test suite for HumanReviewQueue (TDD - tests written before implementation).

Target component: src/omnicompute/queue/hitl.py

Contract under test:
    HumanReviewQueue(queue_path: str = QUEUE_HITL_PATH)

    HumanReviewQueue.enqueue(action: Action, evidence: list[dict]) -> QueueItem
        - Escalation filter: an Action is queued if reversible is False, OR
          confidence < CONFIDENCE_HITL_ESCALATION_MIN (0.75). An Action with
          reversible=True AND confidence >= 0.75 is NOT queued (it is
          expected to be executed autonomously upstream by ResponsePlanner;
          calling enqueue() on it directly is a caller error / no-op
          documented by returning None).
        - Builds a QueueItem with:
            - supporting_evidence copied from the `evidence` argument
              (metric name, z-score, baseline, etc. sourced from the
              triggering Anomaly).
            - queued_at_utc = now (UTC) at enqueue time.
            - timeout_utc = queued_at_utc + HITL_TIMEOUT_HOURS (3 hours / 2
              orbits), unless overridden.
            - timeout_action = "execute_with_log" if the action is
              irreversible, else "escalate_to_critical" if queued purely
              for low confidence.
            - risk_level derived from the action's source anomaly severity
              (or explicit param), used for priority ranking.
        - Appends the new QueueItem to the in-memory queue and persists the
          full queue to disk at `queue_path` (JSON, list of QueueItem
          dicts). The file is created if it does not exist; existing
          on-disk queue items are loaded and preserved (append, not
          overwrite) on construction.

    HumanReviewQueue.check_timeouts(now: datetime | None = None) -> list[QueueItem]
        - Evaluates every PENDING item's timeout_utc against `now` (defaults
          to current UTC time).
        - Expired (now >= timeout_utc) AND timeout_action ==
          "execute_with_log" -> status becomes "EXECUTED"; a log entry
          "timeout_fallback_execution" is emitted (logger.warning or
          logger.info, captured via caplog).
        - Expired AND timeout_action == "escalate_to_critical" -> status
          becomes "ESCALATED" and risk_level is forced to "CRITICAL" for the
          next orbit's uplink.
        - Non-expired PENDING items are left untouched (status remains
          "PENDING") -- no premature execution or escalation.
        - Returns the list of QueueItem objects whose status changed during
          this call (empty list if nothing changed).
        - Persists any state changes back to `queue_path`.

    HumanReviewQueue.process_ground_response(action_id: str, response: str) -> QueueItem | None
        - response in {"APPROVE", "REJECT"}.
        - APPROVE -> status="APPROVED", ground_response="APPROVE" (caller is
          expected to subsequently execute the action; this method only
          updates queue state).
        - REJECT -> status="REJECTED", ground_response="REJECT", and the
          item is removed from the active/pending queue (it may remain in
          a persisted history, but is excluded from future check_timeouts()
          / pending-queue queries).
        - Unknown action_id -> logs a warning, returns None, no state
          mutated.

    HumanReviewQueue.pending_items / .items (read accessors) and queue
    capacity trimming at HITL_QUEUE_CAPACITY_MAX (100): when at capacity,
    the oldest INFO/WARNING (non-CRITICAL) items are trimmed first; CRITICAL
    and any item already escalated for ground uplink are never trimmed.

No implementation code is included in this file. Tests define the contract
for the implementation to satisfy.
"""

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from omnicompute.queue.schemas import QueueItem


# ---------------------------------------------------------------------------
# 1. Escalation filtering
# ---------------------------------------------------------------------------


class TestEscalationFiltering:
    """Which Actions get escalated to the HITL queue."""

    def test_irreversible_action_queued_even_with_high_confidence(
        self, queue_empty, action_irreversible_high_confidence
    ):
        """reversible=False forces escalation regardless of confidence."""
        item = queue_empty.enqueue(
            action_irreversible_high_confidence,
            evidence=[{"metric_name": "rf_signal_strength_dbm", "z_score": -5.9}],
        )

        assert item is not None
        assert item.reversible is False

    def test_low_confidence_action_queued_even_if_reversible(
        self, queue_empty, action_reversible_low_confidence
    ):
        """confidence < 0.75 forces escalation regardless of reversibility."""
        item = queue_empty.enqueue(
            action_reversible_low_confidence,
            evidence=[{"metric_name": "rf_signal_strength_dbm", "z_score": -1.8}],
        )

        assert item is not None
        assert item.confidence < 0.75

    def test_reversible_high_confidence_action_not_queued(
        self, queue_empty, action_load_shed
    ):
        """reversible=True AND confidence >= 0.75 is NOT escalated; it is
        expected to execute autonomously, so enqueue() is a no-op.
        """
        item = queue_empty.enqueue(
            action_load_shed,
            evidence=[{"metric_name": "battery_soc_percent", "z_score": -6.35}],
        )

        assert item is None
        assert queue_empty.pending_items == []


# ---------------------------------------------------------------------------
# 2. Queue item creation
# ---------------------------------------------------------------------------


class TestQueueItemCreation:
    """Fields populated when a QueueItem is created via enqueue()."""

    def test_queue_item_includes_supporting_evidence_from_anomaly(
        self, queue_empty, action_irreversible_throttle
    ):
        """Supporting evidence (metric name, z-score, baseline) is copied
        onto the QueueItem verbatim.
        """
        evidence = [
            {
                "metric_name": "thermal_temp_celsius",
                "z_score": 4.2,
                "baseline_mean": 35.0,
            }
        ]

        item = queue_empty.enqueue(action_irreversible_throttle, evidence=evidence)

        assert item.supporting_evidence == evidence

    def test_queue_item_has_queued_at_utc(self, queue_empty, action_irreversible_throttle):
        """queued_at_utc reflects the time the action was proposed/queued."""
        item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        assert isinstance(item.queued_at_utc, datetime)

    def test_queue_item_has_timeout_utc_default_three_hours(
        self, queue_empty, action_irreversible_throttle
    ):
        """timeout_utc defaults to queued_at_utc + 3 hours (2 orbits)."""
        item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        delta = item.timeout_utc - item.queued_at_utc
        assert delta == timedelta(hours=3)

    def test_queue_item_has_timeout_action_matching_reversibility(
        self, queue_empty, action_irreversible_throttle, action_reversible_low_confidence
    ):
        """Irreversible actions default to execute_with_log; reversible
        low-confidence actions default to escalate_to_critical.
        """
        irreversible_item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])
        reversible_item = queue_empty.enqueue(action_reversible_low_confidence, evidence=[])

        assert irreversible_item.timeout_action == "execute_with_log"
        assert reversible_item.timeout_action == "escalate_to_critical"


# ---------------------------------------------------------------------------
# 3. Queue persistence
# ---------------------------------------------------------------------------


class TestQueuePersistence:
    """Append-only JSON persistence to /queue/hitl_review.json."""

    def test_enqueue_action_saved_to_json_file(
        self, queue_empty, action_irreversible_throttle, hitl_queue_path
    ):
        """After enqueue(), the queue file on disk contains the new item."""
        queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        assert hitl_queue_path.exists()
        on_disk = json.loads(hitl_queue_path.read_text())
        assert len(on_disk) == 1
        assert on_disk[0]["recommended_action"] == "compute_throttle"

    def test_load_existing_queue_appends_new_items(
        self, hitl_queue_path, action_irreversible_throttle, action_reversible_low_confidence
    ):
        """Constructing a new HumanReviewQueue against a populated file
        loads existing items; subsequent enqueue() calls append rather than
        overwrite.
        """
        from omnicompute.queue.hitl import HumanReviewQueue

        first_queue = HumanReviewQueue(queue_path=str(hitl_queue_path))
        first_queue.enqueue(action_irreversible_throttle, evidence=[])

        second_queue = HumanReviewQueue(queue_path=str(hitl_queue_path))
        second_queue.enqueue(action_reversible_low_confidence, evidence=[])

        on_disk = json.loads(hitl_queue_path.read_text())
        assert len(on_disk) == 2

    def test_queue_survives_node_restart_via_persisted_data(
        self, hitl_queue_path, action_irreversible_throttle
    ):
        """A freshly constructed queue instance pointed at an existing file
        loads prior items into memory (simulating a node restart).
        """
        from omnicompute.queue.hitl import HumanReviewQueue

        original_queue = HumanReviewQueue(queue_path=str(hitl_queue_path))
        original_queue.enqueue(action_irreversible_throttle, evidence=[])

        restarted_queue = HumanReviewQueue(queue_path=str(hitl_queue_path))

        assert len(restarted_queue.pending_items) == 1
        assert restarted_queue.pending_items[0].recommended_action == "compute_throttle"


# ---------------------------------------------------------------------------
# 4. Timeout handling
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    """check_timeouts() behavior for expired and non-expired items."""

    def test_irreversible_expired_executes_with_log(
        self, queue_with_items, queue_item_expired_irreversible, caplog
    ):
        """Expired irreversible item -> EXECUTED status + log entry
        'timeout_fallback_execution'.
        """
        queue_with_items._items.append(queue_item_expired_irreversible)
        now = queue_item_expired_irreversible.timeout_utc + timedelta(minutes=1)

        with caplog.at_level(logging.INFO):
            changed = queue_with_items.check_timeouts(now=now)

        updated = next(
            i for i in changed if i.action_id == queue_item_expired_irreversible.action_id
        )
        assert updated.status == "EXECUTED"
        assert "timeout_fallback_execution" in caplog.text

    def test_low_confidence_expired_escalates_to_critical(
        self, queue_with_items, queue_item_expired_low_confidence
    ):
        """Expired low-confidence item -> ESCALATED status, risk_level
        forced to CRITICAL for next orbit's uplink.
        """
        queue_with_items._items.append(queue_item_expired_low_confidence)
        now = queue_item_expired_low_confidence.timeout_utc + timedelta(minutes=1)

        changed = queue_with_items.check_timeouts(now=now)

        updated = next(
            i for i in changed if i.action_id == queue_item_expired_low_confidence.action_id
        )
        assert updated.status == "ESCALATED"
        assert updated.risk_level == "CRITICAL"

    def test_timeout_check_runs_on_next_orbit_evaluates_all_items(
        self, queue_with_items, queue_item_expired_irreversible, queue_item_expired_low_confidence
    ):
        """A single check_timeouts() call evaluates every PENDING item in
        the queue, not just the first.
        """
        queue_with_items._items.append(queue_item_expired_irreversible)
        queue_with_items._items.append(queue_item_expired_low_confidence)
        now = max(
            queue_item_expired_irreversible.timeout_utc,
            queue_item_expired_low_confidence.timeout_utc,
        ) + timedelta(minutes=1)

        changed = queue_with_items.check_timeouts(now=now)
        changed_ids = {i.action_id for i in changed}

        assert queue_item_expired_irreversible.action_id in changed_ids
        assert queue_item_expired_low_confidence.action_id in changed_ids

    def test_non_expired_items_remain_pending_no_premature_action(
        self, queue_empty, queue_item_pending_not_expired
    ):
        """An item whose timeout_utc has not yet passed stays PENDING; no
        execution or escalation occurs.
        """
        queue_empty._items.append(queue_item_pending_not_expired)
        now = queue_item_pending_not_expired.timeout_utc - timedelta(minutes=30)

        changed = queue_empty.check_timeouts(now=now)

        assert changed == []
        assert queue_item_pending_not_expired.status == "PENDING"


# ---------------------------------------------------------------------------
# 5. Ground response processing
# ---------------------------------------------------------------------------


class TestGroundResponseProcessing:
    """process_ground_response() approve/reject/unknown-id handling."""

    def test_ground_approves_action_updates_status_for_execution(
        self, queue_empty, action_irreversible_throttle
    ):
        """APPROVE response marks the item APPROVED, ready for execution."""
        item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        updated = queue_empty.process_ground_response(item.action_id, "APPROVE")

        assert updated.status == "APPROVED"
        assert updated.ground_response == "APPROVE"

    def test_ground_rejects_action_marks_rejected_and_removes_from_queue(
        self, queue_empty, action_irreversible_throttle, caplog
    ):
        """REJECT response marks REJECTED, logs the decision, and removes
        the item from the active/pending queue view.
        """
        item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        with caplog.at_level(logging.INFO):
            updated = queue_empty.process_ground_response(item.action_id, "REJECT")

        assert updated.status == "REJECTED"
        assert updated.ground_response == "REJECT"
        assert all(i.action_id != item.action_id for i in queue_empty.pending_items)

    def test_unknown_action_id_logs_warning_and_is_noop(self, queue_empty, caplog):
        """An action_id that doesn't exist in the queue results in a logged
        warning and a None return, with no state mutated.
        """
        with caplog.at_level(logging.WARNING):
            result = queue_empty.process_ground_response("nonexistent-id", "APPROVE")

        assert result is None
        assert len(caplog.records) >= 1


# ---------------------------------------------------------------------------
# 6. Queue capacity and trimming
# ---------------------------------------------------------------------------


class TestQueueCapacityAndTrimming:
    """Behavior at HITL_QUEUE_CAPACITY_MAX (100 items)."""

    def test_queue_at_capacity_trims_oldest_low_risk_items_first(self, queue_empty):
        """When the queue reaches capacity, the oldest INFO/WARNING items
        are trimmed to make room for new entries.
        """
        from omnicompute.config import HITL_QUEUE_CAPACITY_MAX
        from omnicompute.queue.schemas import QueueItem

        base_time = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(HITL_QUEUE_CAPACITY_MAX):
            queue_empty._items.append(
                QueueItem(
                    action_id=f"act-warn-{i}",
                    recommended_action="reduce_beacon",
                    action_params={},
                    risk_level="WARNING",
                    supporting_evidence=[],
                    confidence=0.5,
                    reversible=True,
                    queued_at_utc=base_time + timedelta(minutes=i),
                    timeout_utc=base_time + timedelta(minutes=i, hours=3),
                    timeout_action="escalate_to_critical",
                    status="PENDING",
                )
            )

        queue_empty._trim_to_capacity()

        assert len(queue_empty.pending_items) <= HITL_QUEUE_CAPACITY_MAX
        # The oldest item (act-warn-0) should have been trimmed first.
        remaining_ids = {i.action_id for i in queue_empty.pending_items}
        assert "act-warn-0" not in remaining_ids or len(queue_empty.pending_items) == HITL_QUEUE_CAPACITY_MAX

    def test_critical_and_hitl_items_never_trimmed(self, queue_empty):
        """CRITICAL items are exempt from capacity trimming and remain in
        the queue even when the queue is over its WARNING/INFO trim
        threshold.
        """
        from omnicompute.config import HITL_QUEUE_CAPACITY_MAX
        from omnicompute.queue.schemas import QueueItem

        base_time = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

        critical_item = QueueItem(
            action_id="act-critical-keep",
            recommended_action="compute_throttle",
            action_params={},
            risk_level="CRITICAL",
            supporting_evidence=[],
            confidence=0.5,
            reversible=False,
            queued_at_utc=base_time,
            timeout_utc=base_time + timedelta(hours=3),
            timeout_action="execute_with_log",
            status="PENDING",
        )
        queue_empty._items.append(critical_item)

        for i in range(HITL_QUEUE_CAPACITY_MAX):
            queue_empty._items.append(
                QueueItem(
                    action_id=f"act-warn-{i}",
                    recommended_action="reduce_beacon",
                    action_params={},
                    risk_level="WARNING",
                    supporting_evidence=[],
                    confidence=0.5,
                    reversible=True,
                    queued_at_utc=base_time + timedelta(minutes=i + 1),
                    timeout_utc=base_time + timedelta(minutes=i + 1, hours=3),
                    timeout_action="escalate_to_critical",
                    status="PENDING",
                )
            )

        queue_empty._trim_to_capacity()

        remaining_ids = {i.action_id for i in queue_empty.pending_items}
        assert "act-critical-keep" in remaining_ids


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Empty queue and fully-expired queue scenarios."""

    def test_empty_queue_has_nothing_to_escalate(self, queue_empty):
        """check_timeouts() on an empty queue returns an empty list and does
        not raise.
        """
        changed = queue_empty.check_timeouts()

        assert changed == []

    def test_queue_with_all_items_timed_out_all_escalated_or_executed(
        self, queue_empty, queue_item_expired_irreversible, queue_item_expired_low_confidence
    ):
        """When every item in the queue has expired, check_timeouts()
        transitions every one of them to either EXECUTED or ESCALATED;
        none remain PENDING.
        """
        queue_empty._items.append(queue_item_expired_irreversible)
        queue_empty._items.append(queue_item_expired_low_confidence)
        now = max(
            queue_item_expired_irreversible.timeout_utc,
            queue_item_expired_low_confidence.timeout_utc,
        ) + timedelta(minutes=1)

        queue_empty.check_timeouts(now=now)

        assert all(i.status != "PENDING" for i in queue_empty._items)
        assert all(i.status in {"EXECUTED", "ESCALATED"} for i in queue_empty._items)
