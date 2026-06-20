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

    def test_bundle_over_limit_raises_error(self):
        """Bundle over 512KB raises BundleError."""
        from omnicompute.uplink.bundler import UplinkBundler
        from omnicompute.errors import BundleError

        bundler = UplinkBundler()
        huge_anomalies = [
            Anomaly(
                node_id=f"H-{i}",
                metric_name="m" * 1000,
                current_value=9.99e9,
                baseline_mean=9.99e9,
                baseline_stddev=9.99e8,
                z_score=0.0,
                severity="NOMINAL",
                confidence=0.999,
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(500)
        ]

        with pytest.raises(BundleError):
            bundler.bundle(huge_anomalies, [], [])


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
