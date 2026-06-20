"""Test suite for UplinkBundler (TDD - tests written before implementation).

Target component: src/omnicompute/uplink/bundler.py

Contract: UplinkBundler serializes, compresses, and encrypts anomalies/actions/queue items into 512KB uplink bundles.
"""

import gzip
import json
import pytest
from datetime import datetime, timezone

from omnicompute.anomaly.schemas import Anomaly
from omnicompute.uplink.schemas import UplinkBundle


class TestBundleCreation:
    """Basic bundle creation."""

    def test_single_anomaly_creates_bundle(self, anomaly_critical_battery):
        """Single anomaly → valid bundle."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([anomaly_critical_battery], [], [])
        assert isinstance(bundle, UplinkBundle)
        assert bundle.metadata.item_count >= 1

    def test_multiple_anomalies_single_bundle(self, anomaly_critical_battery, anomaly_warning_thermal):
        """Multiple anomalies → single bundle if under limit."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([anomaly_critical_battery, anomaly_warning_thermal], [], [])
        assert bundle.metadata.compressed_size_bytes <= 512 * 1024

    def test_empty_inputs_minimal_bundle(self):
        """Empty inputs → valid minimal bundle."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [])
        assert isinstance(bundle, UplinkBundle)
        assert bundle.metadata.item_count == 0


class TestCompression:
    """Gzip compression behavior."""

    def test_payload_compresses(self, anomaly_critical_battery):
        """Payload compresses to <90% of original."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([anomaly_critical_battery], [], [])
        
        if bundle.metadata.size_bytes > 0:
            ratio = bundle.metadata.compressed_size_bytes / bundle.metadata.size_bytes
            assert ratio < 0.9

    def test_compression_respects_limit(self):
        """Compressed bundle respects 512KB limit."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        anomalies = [
            Anomaly(
                node_id=f"Node-{i}",
                metric_name="battery_soc_percent",
                current_value=50.0,
                baseline_mean=65.0,
                baseline_stddev=8.0,
                z_score=-1.875,
                severity="NOMINAL",
                confidence=0.9,
                timestamp=datetime(2026, 6, 20, 10, 0, 0, tzinfo=timezone.utc),
            )
            for i in range(10)
        ]
        bundle = bundler.bundle(anomalies, [], [])
        assert bundle.metadata.compressed_size_bytes <= 512 * 1024


class TestEncryption:
    """Encryption handling."""

    def test_unencrypted_bundle_readable(self):
        """Unencrypted bundle is gzip+JSON."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [])
        assert bundle.encryption_algorithm is None
        
        # Should decompress
        decompressed = gzip.decompress(bundle.data)
        json.loads(decompressed)

    def test_encrypted_bundle_opaque(self, encryption_key):
        """Encrypted bundle data is opaque."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler(encryption_key=encryption_key)
        bundle = bundler.bundle([], [], [])
        assert bundle.encryption_algorithm is not None


class TestSizeLimit:
    """512KB size enforcement."""

    def test_bundle_under_limit_accepted(self, anomaly_critical_battery):
        """Bundle under 512KB accepted."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([anomaly_critical_battery], [], [])
        assert bundle.metadata.compressed_size_bytes <= 512 * 1024

    def test_bundle_size_limit_enforced(self):
        """Bundle size limit of 512KB is enforced."""
        from omnicompute.uplink.bundler import UplinkBundler
        from omnicompute.errors import BundleError

        bundler = UplinkBundler()

        # Test that the bundler respects the 512KB limit
        # By creating content that when uncompressed would be large
        try:
            # Create many anomalies with diverse data to exceed compression efficiency
            anomalies = [
                Anomaly(
                    node_id=f"Node-{i:05d}",
                    metric_name=f"metric_{i}_{chr(65 + (i % 26))}",
                    current_value=float(i) * 1.234567,
                    baseline_mean=float(i) * 1.111111,
                    baseline_stddev=float(i) * 0.999999,
                    z_score=float(i % 10) - 5.0,
                    severity="NOMINAL",
                    confidence=0.9 + (i % 10) * 0.01,
                    timestamp=datetime.now(timezone.utc),
                )
                for i in range(5000)  # 5000 diverse anomalies
            ]

            bundle = bundler.bundle(anomalies, [], [])
            # If we got here, the bundle fits within 512KB
            assert bundle.metadata.compressed_size_bytes <= 512 * 1024
        except BundleError:
            # If size limit is hit, that's also valid - limit is enforced
            pass


class TestMetadata:
    """Bundle metadata completeness."""

    def test_metadata_includes_all_fields(self, anomaly_critical_battery):
        """Metadata has node_count, item_count, sizes."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([anomaly_critical_battery], [], [])

        assert bundle.metadata.node_count >= 1
        assert bundle.metadata.item_count >= 1
        assert bundle.metadata.size_bytes > 0
        assert bundle.metadata.compressed_size_bytes > 0

    def test_power_budget_tracked(self):
        """Power budget included when provided."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [], power_budget_remaining=85.5)
        assert bundle.metadata.power_budget_remaining_percent == 85.5


class TestErrorHandling:
    """Error handling and edge cases."""

    def test_encryption_key_format_invalid_handled(self):
        """Invalid encryption key handled gracefully."""
        from omnicompute.uplink.bundler import UplinkBundler

        # Invalid key format should not crash bundler construction
        bundler = UplinkBundler(encryption_key="not_a_valid_fernet_key")
        # Should still create bundles, just unencrypted
        bundle = bundler.bundle([], [], [])
        assert bundle is not None

    def test_bundle_with_actions_and_queue_items(self, action_irreversible_throttle, queue_empty):
        """Bundle includes actions and queue items."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        item = queue_empty.enqueue(action_irreversible_throttle, evidence=[])

        bundle = bundler.bundle([], [action_irreversible_throttle], [item] if item else [])
        assert bundle.metadata.item_count >= 1

    def test_bundle_timestamp_is_utc(self):
        """Bundle timestamp is in UTC."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [])

        assert bundle.timestamp.tzinfo is not None
        assert str(bundle.timestamp.tzinfo) == "UTC"

    def test_large_number_of_unique_nodes(self):
        """Bundle handles 100+ unique nodes."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        anomalies = [
            Anomaly(
                node_id=f"Node-{i:03d}",
                metric_name="battery",
                current_value=50.0,
                baseline_mean=65.0,
                baseline_stddev=8.0,
                z_score=0.0,
                severity="NOMINAL",
                confidence=0.9,
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(100)
        ]

        bundle = bundler.bundle(anomalies, [], [])
        assert bundle.metadata.node_count == 100

    def test_bundle_compressed_and_encrypted(self, encryption_key):
        """Bundle with both compression and encryption."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler(encryption_key=encryption_key)
        anomalies = [
            Anomaly(
                node_id="Sat-01",
                metric_name="test_metric",
                current_value=1.0,
                baseline_mean=1.0,
                baseline_stddev=1.0,
                z_score=0.0,
                severity="NOMINAL",
                confidence=0.9,
                timestamp=datetime.now(timezone.utc),
            )
        ]

        bundle = bundler.bundle(anomalies, [], [])
        assert bundle.encryption_algorithm == "Fernet"
        assert bundle.metadata.compressed_size_bytes < bundle.metadata.size_bytes

    def test_zero_percent_power_budget(self):
        """Zero power budget is valid."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [], power_budget_remaining=0.0)
        assert bundle.metadata.power_budget_remaining_percent == 0.0

    def test_100_percent_power_budget(self):
        """100% power budget is valid."""
        from omnicompute.uplink.bundler import UplinkBundler

        bundler = UplinkBundler()
        bundle = bundler.bundle([], [], [], power_budget_remaining=100.0)
        assert bundle.metadata.power_budget_remaining_percent == 100.0
