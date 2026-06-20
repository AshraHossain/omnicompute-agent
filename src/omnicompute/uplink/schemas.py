"""Pydantic data models for uplink bundling (UplinkBundle, BundleMetadata)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BundleMetadata(BaseModel):
    """Metadata describing the contents and size of an UplinkBundle.

    Attached to every bundle so ground operators can audit bundle contents
    without decrypting/decompressing the payload first.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "node_count": 3,
                "item_count": 7,
                "size_bytes": 4096,
                "compressed_size_bytes": 1536,
                "power_budget_remaining_percent": 92.5,
            }
        }
    )

    node_count: int = Field(..., ge=0, description="Distinct nodes represented in this bundle")
    item_count: int = Field(
        ..., ge=0, description="Total items bundled (anomalies + actions + queue items)"
    )
    size_bytes: int = Field(..., ge=0, description="Uncompressed serialized payload size in bytes")
    compressed_size_bytes: int = Field(
        ..., ge=0, description="Size in bytes after gzip compression, pre-encryption"
    )
    power_budget_remaining_percent: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Remaining autonomous-action power budget (%) at bundle creation time",
    )


class UplinkBundle(BaseModel):
    """A compressed, encrypted payload ready for transmission to ground.

    `data` holds the final bytes (gzip-compressed, then Fernet-encrypted
    unless encryption is disabled/unavailable, in which case it holds the
    compressed-but-unencrypted bytes and `encryption_algorithm` is None).
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data: bytes = Field(..., description="Final bundle payload bytes (compressed, optionally encrypted)")
    metadata: BundleMetadata = Field(..., description="Descriptive metadata about this bundle's contents")
    timestamp: datetime = Field(..., description="UTC timestamp when the bundle was assembled")
    encryption_algorithm: Optional[str] = Field(
        None,
        description="Encryption algorithm identifier (e.g. 'Fernet/AES-128-CBC+HMAC'), "
        "or None if the bundle is unencrypted (degraded mode)",
    )
