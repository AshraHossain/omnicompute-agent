"""End-to-end pipeline orchestration: Parser → Triager → Planner → Queue → Bundler."""

import logging
from typing import Dict, Any, Optional

from omnicompute.telemetry.parser import TelemetryParser
from omnicompute.telemetry.schemas import Telemetry
from omnicompute.anomaly.baseline import BaselineCache
from omnicompute.anomaly.triager import AnomalyTriager
from omnicompute.response.planner import ResponsePlanner
from omnicompute.queue.hitl import HumanReviewQueue
from omnicompute.uplink.bundler import UplinkBundler
from omnicompute.uplink.schemas import UplinkBundle

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrate full pipeline from telemetry to uplink bundle."""

    def __init__(
        self,
        baseline_cache: Optional[BaselineCache] = None,
        node_config: Optional[Dict[str, Any]] = None,
        playbooks_dir: Optional[str] = None,
        encryption_key: Optional[str] = None
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            baseline_cache: Baseline statistics (30-day rolling)
            node_config: Node configuration (power budget, safe ranges)
            playbooks_dir: Path to playbooks directory
            encryption_key: Encryption key for bundles
        """
        self._parser = TelemetryParser()
        self._baseline_cache = baseline_cache or BaselineCache()
        self._node_config = node_config or {}
        self._triager = AnomalyTriager(self._baseline_cache, self._node_config)
        self._planner = ResponsePlanner(self._baseline_cache, self._node_config, playbooks_dir)
        self._queue = HumanReviewQueue()
        self._bundler = UplinkBundler(encryption_key=encryption_key)

    def process_telemetry(
        self,
        raw_json: str,
        power_budget_remaining: Optional[float] = None
    ) -> UplinkBundle:
        """
        Process telemetry batch end-to-end and generate uplink bundle.

        Args:
            raw_json: Raw telemetry JSON from contact window
            power_budget_remaining: Remaining power budget (0-100%)

        Returns:
            UplinkBundle ready for transmission
        """
        # Step 1: Parse telemetry
        telemetry = self._parser.parse(raw_json)
        logger.info(f"Parsed {len(telemetry)} telemetry records")

        # Step 2: Triage anomalies
        anomalies = self._triager.triage(telemetry)
        logger.info(f"Triaged {len(anomalies)} anomalies")

        # Step 3: Plan responses
        actions = self._planner.plan(anomalies)
        logger.info(f"Planned {len(actions)} actions")

        # Step 4: Escalate low-confidence/irreversible to HITL queue
        escalated = []
        for action in actions:
            item = self._queue.enqueue(action, evidence=[])
            if item:
                escalated.append(item)
        logger.info(f"Escalated {len(escalated)} items to HITL queue")

        # Step 5: Bundle for transmission
        queue_items = self._queue.pending_items
        bundle = self._bundler.bundle(
            anomalies,
            actions,
            queue_items,
            power_budget_remaining=power_budget_remaining
        )
        logger.info(f"Generated bundle: {bundle.metadata.compressed_size_bytes} bytes")

        return bundle
