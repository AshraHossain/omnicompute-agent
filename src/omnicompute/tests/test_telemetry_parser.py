"""Test suite for TelemetryParser (TDD - tests written before implementation).

Target component: src/omnicompute/telemetry/parser.py
Contract:
    TelemetryParser().parse(raw_json: str) -> list[Telemetry]

Behavioral contract under test:
    - Ingests raw JSON string (as read from /data/telemetry_batch_latest.json)
    - Validates required fields per node reading: node_id, timestamp, metrics
    - Normalizes timestamps to UTC ISO 8601 / datetime
    - Coerces invalid/non-numeric metric values to 0.0
    - Skips malformed records individually (does not abort whole batch)
    - Never raises on malformed JSON or malformed records; returns partial
      results and logs warnings/errors instead
    - Idempotent: parsing the same input twice yields identical output

No implementation code is included in this file. Tests define the
contract for the implementation to satisfy.
"""

import json
import logging

import pytest

from omnicompute.telemetry.schemas import Telemetry
from omnicompute.tests.conftest import to_json_str


# ---------------------------------------------------------------------------
# 1. Happy Path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Parsing well-formed batches should produce correct Telemetry objects."""

    def test_parse_valid_single_node_batch_returns_one_telemetry(
        self, parser, valid_batch_single_node
    ):
        """A batch with exactly one node reading yields exactly one Telemetry."""
        result = parser.parse(to_json_str(valid_batch_single_node))

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Telemetry)

    def test_parse_valid_multi_node_batch_returns_list_of_telemetry(
        self, parser, valid_batch_multi_node
    ):
        """A batch with 3 node readings yields 3 Telemetry objects, in order."""
        result = parser.parse(to_json_str(valid_batch_multi_node))

        assert len(result) == 3
        assert all(isinstance(item, Telemetry) for item in result)
        node_ids = [item.node_id for item in result]
        assert node_ids == ["Sat-01", "FGN-Alpha", "MCH-Primary"]

    def test_parsed_telemetry_has_all_fields_populated_and_correct(
        self, parser, valid_batch_single_node
    ):
        """node_id, timestamp, received_at, and metrics all reflect input data."""
        result = parser.parse(to_json_str(valid_batch_single_node))
        telemetry = result[0]

        assert telemetry.node_id == "Sat-01"
        assert telemetry.timestamp is not None
        assert telemetry.received_at is not None
        assert telemetry.metrics["power_draw_watts"] == pytest.approx(9.2)
        assert telemetry.metrics["battery_soc_percent"] == pytest.approx(14.2)
        assert telemetry.metrics["thermal_temp_celsius"] == pytest.approx(42.1)
        assert telemetry.metrics["rf_signal_strength_dbm"] == pytest.approx(-75.3)


# ---------------------------------------------------------------------------
# 2. Schema & Validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    """Required-field validation and tolerance for non-essential fields."""

    def test_missing_node_id_skips_record_and_logs_warning(
        self, parser, batch_missing_node_id, caplog
    ):
        """Record without node_id is skipped; the valid sibling record survives."""
        with caplog.at_level(logging.WARNING):
            result = parser.parse(to_json_str(batch_missing_node_id))

        assert len(result) == 1
        assert result[0].node_id == "Sat-01"
        assert any(
            record.levelno >= logging.WARNING for record in caplog.records
        ), "Expected a warning (or higher) log entry for the skipped record"

    def test_missing_timestamp_skips_record_and_logs_warning(
        self, parser, batch_missing_timestamp, caplog
    ):
        """Record without a usable timestamp is skipped and logged."""
        with caplog.at_level(logging.WARNING):
            result = parser.parse(to_json_str(batch_missing_timestamp))

        assert result == []
        assert any(
            record.levelno >= logging.WARNING for record in caplog.records
        )

    def test_empty_metrics_dict_is_accepted_as_valid(self, parser):
        """A node reading with an empty metrics dict is valid (no metrics)."""
        batch = {
            "batch_id": "batch_empty_metrics",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert len(result) == 1
        assert result[0].metrics == {}

    def test_extra_unknown_fields_are_ignored_and_parsing_succeeds(self, parser):
        """Unexpected extra keys in the JSON do not break parsing."""
        batch = {
            "batch_id": "batch_extra_fields",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "mission_phase": "nominal_ops",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"battery_soc_percent": 50.0},
                    "firmware_version": "v3.2.1",
                    "orbit_phase": "eclipse",
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert len(result) == 1
        assert result[0].node_id == "Sat-01"
        assert result[0].metrics["battery_soc_percent"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# 3. Unit Conversion
# ---------------------------------------------------------------------------


class TestUnitConversion:
    """Metric values pass through with correct, realistic units."""

    def test_thermal_temp_celsius_value_passes_through_unconverted(self, parser):
        """thermal_temp_celsius stays in Celsius (no spurious conversion)."""
        batch = {
            "batch_id": "batch_thermal",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"thermal_temp_celsius": 42.1},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["thermal_temp_celsius"] == pytest.approx(42.1)

    def test_battery_soc_percent_value_is_within_zero_to_hundred_range(self, parser):
        """battery_soc_percent is treated as a percent value (0-100 nominal)."""
        batch = {
            "batch_id": "batch_battery",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"battery_soc_percent": 14.2},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        soc = result[0].metrics["battery_soc_percent"]
        assert 0.0 <= soc <= 100.0

    def test_rf_signal_strength_dbm_is_within_realistic_range(self, parser):
        """rf_signal_strength_dbm falls within a realistic negative dBm range."""
        batch = {
            "batch_id": "batch_rf",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"rf_signal_strength_dbm": -75.3},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        rf = result[0].metrics["rf_signal_strength_dbm"]
        assert -120.0 <= rf <= -30.0


# ---------------------------------------------------------------------------
# 4. Timestamp Normalization
# ---------------------------------------------------------------------------


class TestTimestampNormalization:
    """Timestamps must normalize consistently to UTC."""

    def test_iso8601_timestamp_is_parsed_to_datetime(self, parser):
        """A standard ISO 8601 'Z' timestamp parses into a datetime field."""
        batch = {
            "batch_id": "batch_iso",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        telemetry = result[0]
        assert telemetry.timestamp.year == 2026
        assert telemetry.timestamp.month == 6
        assert telemetry.timestamp.day == 19
        assert telemetry.timestamp.hour == 20
        assert telemetry.timestamp.minute == 10

    def test_timestamp_with_explicit_utc_offset_normalizes_to_same_instant(
        self, parser
    ):
        """A timestamp with a +00:00 offset normalizes to the same UTC instant
        as the equivalent 'Z'-suffixed timestamp."""
        batch_offset = {
            "batch_id": "batch_offset",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00+00:00",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {},
                }
            ],
        }
        batch_z = {
            "batch_id": "batch_z",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {},
                }
            ],
        }

        result_offset = parser.parse(to_json_str(batch_offset))
        result_z = parser.parse(to_json_str(batch_z))

        assert result_offset[0].timestamp == result_z[0].timestamp

    def test_invalid_timestamp_format_skips_record_and_logs_error(
        self, parser, caplog
    ):
        """An unparseable timestamp string causes the record to be skipped."""
        batch = {
            "batch_id": "batch_bad_timestamp",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "not-a-real-timestamp",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {},
                }
            ],
        }
        with caplog.at_level(logging.WARNING):
            result = parser.parse(to_json_str(batch))

        assert result == []
        assert any(
            record.levelno >= logging.WARNING for record in caplog.records
        )


# ---------------------------------------------------------------------------
# 5. Coercion & Fallbacks
# ---------------------------------------------------------------------------


class TestCoercionAndFallbacks:
    """Invalid metric values must be safely coerced rather than crashing."""

    def test_string_metric_value_is_coerced_to_zero(self, parser):
        """A metric with a non-numeric string value coerces to 0.0."""
        batch = {
            "batch_id": "batch_string_metric",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"battery_soc_percent": "abc"},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["battery_soc_percent"] == 0.0

    def test_none_metric_value_is_coerced_to_zero(self, parser):
        """A metric with a None value coerces to 0.0."""
        batch = {
            "batch_id": "batch_none_metric",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"thermal_temp_celsius": None},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["thermal_temp_celsius"] == 0.0

    def test_very_large_float_metric_value_is_accepted_as_is(self, parser):
        """A very large float metric value is preserved, not clamped."""
        batch = {
            "batch_id": "batch_large_metric",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"uplink_queue_bytes": 1.5e8},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["uplink_queue_bytes"] == pytest.approx(1.5e8)

    def test_negative_metric_value_is_accepted_when_semantically_valid(
        self, parser
    ):
        """A negative metric value (e.g. dBm signal strength) is preserved."""
        batch = {
            "batch_id": "batch_negative_metric",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"rf_signal_strength_dbm": -92.5},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["rf_signal_strength_dbm"] == pytest.approx(-92.5)


# ---------------------------------------------------------------------------
# 6. Malformed JSON
# ---------------------------------------------------------------------------


class TestMalformedJson:
    """Top-level JSON parse failures must never raise out of parse()."""

    def test_invalid_json_syntax_returns_empty_list_and_logs_error(
        self, parser, batch_invalid_json, caplog
    ):
        """Unparseable JSON text is caught; parse() returns [] without raising."""
        with caplog.at_level(logging.ERROR):
            result = parser.parse(batch_invalid_json)

        assert result == []
        assert any(record.levelno >= logging.ERROR for record in caplog.records)

    def test_empty_json_object_parses_to_empty_node_readings(
        self, parser, batch_empty_json_object
    ):
        """A bare '{}' JSON object parses successfully to an empty list."""
        result = parser.parse(to_json_str(batch_empty_json_object))

        assert result == []


# ---------------------------------------------------------------------------
# 7. Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary conditions: empty lists, large batches, duplicates, overflow."""

    def test_empty_node_readings_list_returns_empty_list(self, parser, batch_empty):
        """A batch with node_readings: [] returns an empty result list."""
        result = parser.parse(to_json_str(batch_empty))

        assert result == []

    def test_batch_with_over_one_hundred_nodes_parses_all_without_truncation(
        self, parser
    ):
        """A batch with 100+ node readings parses every record, no truncation."""
        node_count = 120
        batch = {
            "batch_id": "batch_large",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": f"Sat-{i:03d}",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"battery_soc_percent": float(i % 100)},
                }
                for i in range(node_count)
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert len(result) == node_count

    def test_duplicate_node_id_in_same_batch_accepts_both_no_dedup(self, parser):
        """Two readings sharing the same node_id are both kept (no dedup)."""
        batch = {
            "batch_id": "batch_dupes",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"battery_soc_percent": 14.2},
                },
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:11:00Z",
                    "received_at_utc": "2026-06-19T20:16:00Z",
                    "metrics": {"battery_soc_percent": 13.8},
                },
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert len(result) == 2
        assert result[0].node_id == "Sat-01"
        assert result[1].node_id == "Sat-01"
        assert result[0].metrics["battery_soc_percent"] != result[1].metrics[
            "battery_soc_percent"
        ]

    def test_very_large_metric_value_does_not_overflow(self, parser):
        """A metric value of 1e10 is accepted without overflow or error."""
        batch = {
            "batch_id": "batch_overflow_check",
            "batch_timestamp_utc": "2026-06-19T20:15:00Z",
            "node_readings": [
                {
                    "node_id": "Sat-01",
                    "timestamp": "2026-06-19T20:10:00Z",
                    "received_at_utc": "2026-06-19T20:15:00Z",
                    "metrics": {"uplink_queue_bytes": 1e10},
                }
            ],
        }
        result = parser.parse(to_json_str(batch))

        assert result[0].metrics["uplink_queue_bytes"] == pytest.approx(1e10)


# ---------------------------------------------------------------------------
# 8. Idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    """Parsing the same input must always yield identical output."""

    def test_parsing_same_batch_twice_yields_identical_output(
        self, parser, valid_batch_multi_node
    ):
        """Calling parse() twice with the same JSON string is deterministic."""
        raw = to_json_str(valid_batch_multi_node)

        result_first = parser.parse(raw)
        result_second = parser.parse(raw)

        assert len(result_first) == len(result_second)
        for first, second in zip(result_first, result_second):
            assert first.node_id == second.node_id
            assert first.timestamp == second.timestamp
            assert first.received_at == second.received_at
            assert first.metrics == second.metrics
