"""Custom exception classes for OmniCompute."""


class OmniComputeError(Exception):
    """Base exception for all OmniCompute errors."""
    pass


class TelemetryParseError(OmniComputeError):
    """Raised when telemetry parsing fails."""
    pass


class AnomalyTriageError(OmniComputeError):
    """Raised when anomaly detection fails."""
    pass


class BaselineError(OmniComputeError):
    """Raised when baseline cache operations fail."""
    pass


class PlaybookError(OmniComputeError):
    """Raised when playbook loading/evaluation fails."""
    pass


class ResponsePlanError(OmniComputeError):
    """Raised when response planning fails."""
    pass


class ExecutionError(OmniComputeError):
    """Raised when action execution fails."""
    pass


class EncryptionError(OmniComputeError):
    """Raised when encryption/decryption fails."""
    pass


class BundleError(OmniComputeError):
    """Raised when uplink bundle assembly fails."""
    pass


class QueueError(OmniComputeError):
    """Raised when HITL queue operations fail."""
    pass
