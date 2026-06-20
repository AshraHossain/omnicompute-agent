"""UplinkBundler: Compress and encrypt uplink payloads for transmission."""

import gzip
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from omnicompute.anomaly.schemas import Anomaly
from omnicompute.response.schemas import Action
from omnicompute.queue.schemas import QueueItem
from omnicompute.uplink.schemas import UplinkBundle, BundleMetadata
from omnicompute.errors import BundleError

logger = logging.getLogger(__name__)

UPLINK_BUNDLE_SIZE_MAX_BYTES = 512 * 1024


class UplinkBundler:
    """Bundle, compress, and encrypt anomalies, actions, and queue items."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize bundler.

        Args:
            encryption_key: Fernet encryption key (base64-encoded), or None for no encryption
        """
        self._encryption_key = encryption_key
        self._cipher = None

        if encryption_key:
            try:
                from cryptography.fernet import Fernet
                self._cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
                self._cipher = None

    def bundle(
        self,
        anomalies: List[Anomaly],
        actions: List[Action],
        queue_items: List[QueueItem],
        power_budget_remaining: Optional[float] = None
    ) -> UplinkBundle:
        """
        Bundle anomalies, actions, and queue items for uplink.

        Args:
            anomalies: List of detected anomalies
            actions: List of recommended actions
            queue_items: List of HITL queue items
            power_budget_remaining: Remaining power budget percentage (0-100)

        Returns:
            UplinkBundle ready for transmission

        Raises:
            BundleError: If bundle exceeds 512KB after compression
        """
        # Serialize payload
        payload = {
            "anomalies": [a.model_dump(mode="json") for a in anomalies],
            "actions": [a.model_dump(mode="json") for a in actions],
            "queue_items": [q.model_dump(mode="json") for q in queue_items],
        }

        payload_json = json.dumps(payload, default=str)
        uncompressed_size = len(payload_json.encode())

        # Compress
        try:
            compressed = gzip.compress(payload_json.encode())
            compressed_size = len(compressed)
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            raise BundleError(f"Failed to compress payload: {e}")

        # Check size limit
        if compressed_size > UPLINK_BUNDLE_SIZE_MAX_BYTES:
            raise BundleError(
                f"Compressed bundle {compressed_size} bytes exceeds limit {UPLINK_BUNDLE_SIZE_MAX_BYTES} bytes"
            )

        # Encrypt if key available
        data = compressed
        encryption_algorithm = None

        if self._cipher:
            try:
                data = self._cipher.encrypt(compressed)
                encryption_algorithm = "Fernet"
            except Exception as e:
                logger.warning(f"Encryption failed, sending unencrypted: {e}")

        # Build metadata
        unique_nodes = {a.node_id for a in anomalies} | {a.node_id for a in actions} | {q.action_id for q in queue_items}

        metadata = BundleMetadata(
            node_count=len(unique_nodes),
            item_count=len(anomalies) + len(actions) + len(queue_items),
            size_bytes=uncompressed_size,
            compressed_size_bytes=compressed_size,
            encryption_algorithm=encryption_algorithm,
            power_budget_remaining_percent=power_budget_remaining,
        )

        return UplinkBundle(
            data=data,
            metadata=metadata,
            timestamp=datetime.now(timezone.utc),
            encryption_algorithm=encryption_algorithm,
        )
