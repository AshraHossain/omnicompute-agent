"""TelemetryParser: Ingest and normalize raw sensor telemetry."""

import json
import logging
from datetime import datetime
from typing import List, Any, Dict

from omnicompute.errors import TelemetryParseError
from omnicompute.telemetry.schemas import Telemetry

logger = logging.getLogger(__name__)


class TelemetryParser:
    """Parse and normalize raw telemetry batches from distributed nodes."""

    def parse(self, raw_json: str) -> List[Telemetry]:
        """
        Parse raw JSON telemetry batch and return normalized Telemetry objects.

        Handles errors gracefully: malformed records are skipped with log warnings,
        and the parser continues processing remaining records. Invalid JSON syntax
        is logged and an empty list is returned (no exception raised).

        Args:
            raw_json: Raw JSON string from /data/telemetry_batch_latest.json

        Returns:
            List of normalized Telemetry objects. Empty list if parse fails or
            no valid records found.
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON syntax in telemetry batch: {e}")
            return []

        # Extract node_readings array
        node_readings = data.get("node_readings", [])
        if not isinstance(node_readings, list):
            logger.error("Expected 'node_readings' to be a list; got %s", type(node_readings))
            return []

        results = []
        for i, record in enumerate(node_readings):
            try:
                telemetry = self._parse_record(record, i)
                if telemetry:
                    results.append(telemetry)
            except Exception as e:
                logger.warning(f"Skipped telemetry record {i}: {e}")
                continue

        return results

    def _parse_record(self, record: Dict[str, Any], index: int) -> Telemetry | None:
        """
        Parse a single telemetry record.

        Raises ValueError if validation fails (caller catches and logs).
        Returns None if optional validation fails (soft skip).
        """
        if not isinstance(record, dict):
            raise ValueError(f"Expected dict, got {type(record)}")

        # Required: node_id
        node_id = record.get("node_id")
        if not node_id or not isinstance(node_id, str):
            raise ValueError(f"Missing or invalid 'node_id': {node_id}")

        # Required: timestamp (parse to datetime, then normalize back to ISO string)
        timestamp_raw = record.get("timestamp")
        if not timestamp_raw:
            raise ValueError(f"Missing 'timestamp' in record for node {node_id}")

        timestamp = self._parse_timestamp(timestamp_raw)
        if timestamp is None:
            raise ValueError(f"Invalid timestamp format: {timestamp_raw}")

        # Required: received_at_utc (for received_at field)
        received_at_raw = record.get("received_at_utc")
        if not received_at_raw:
            raise ValueError(f"Missing 'received_at_utc' in record for node {node_id}")

        received_at = self._parse_timestamp(received_at_raw)
        if received_at is None:
            raise ValueError(f"Invalid received_at_utc format: {received_at_raw}")

        # Optional: metrics dict (empty dict is valid)
        metrics = record.get("metrics", {})
        if not isinstance(metrics, dict):
            logger.warning(f"Metrics for {node_id} is not a dict; treating as empty")
            metrics = {}

        # Create Telemetry object (Pydantic validator will coerce metrics to float)
        return Telemetry(
            node_id=node_id,
            timestamp=timestamp,
            received_at=received_at,
            metrics=metrics
        )

    def _parse_timestamp(self, ts_str: str) -> datetime | None:
        """
        Parse timestamp string to datetime.

        Tries ISO 8601 format. Handles timezone offsets by normalizing to UTC.
        Returns UTC-aware datetime (all timestamps treated as UTC).
        Returns None if parsing fails.
        """
        from datetime import timezone as tz

        if not isinstance(ts_str, str):
            return None

        # Try common ISO 8601 formats
        formats = [
            ("%Y-%m-%dT%H:%M:%SZ", True),           # 2026-06-19T20:10:00Z
            ("%Y-%m-%dT%H:%M:%S%z", True),         # 2026-06-19T20:10:00+00:00
            ("%Y-%m-%dT%H:%M:%S.%fZ", True),       # 2026-06-19T20:10:00.000Z
            ("%Y-%m-%dT%H:%M:%S.%f%z", True),      # 2026-06-19T20:10:00.000+00:00
        ]

        for fmt, is_utc in formats:
            try:
                # For Z suffix, remove it before parsing
                ts_clean = ts_str.replace("Z", "")
                dt = datetime.strptime(ts_clean, fmt)
                # Ensure UTC awareness
                if dt.tzinfo is None and is_utc:
                    dt = dt.replace(tzinfo=tz.utc)
                return dt
            except ValueError:
                continue

        # Try fromisoformat as fallback (Python 3.7+)
        try:
            # Replace Z with +00:00 for fromisoformat
            ts_iso = ts_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_iso)
            # Ensure UTC awareness
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz.utc)
            return dt
        except (ValueError, AttributeError):
            return None
