"""Compatibility exports for the channel-independent continuation worker."""
from src.runtime.incident_continuation_worker import (
    MAX_PREAPPROVAL_RECOVERY_ATTEMPTS,
    IncidentContinuationWorker,
    IncidentContinuationWorkerDependencies,
    IncidentContinuationWorkerOutcome,
    IncidentProcessor,
    TerminalNotifier,
    WorkflowFactory,
)
