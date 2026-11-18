"""Immutable admission identity; never approval or operational authority."""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.runtime.execution_affinity import ExecutionAffinity, require_digest, require_identifier

EXECUTION_ID_STATE_KEY = "incident_execution_id"


MANUAL_ANALYSIS_REASON_KEY = "incident_manual_analysis_reason"


class IncidentExecutionConflictError(ValueError):
    pass


class AdmissionClosedError(RuntimeError):
    pass


@dataclass(frozen=True, kw_only=True)
class IncidentExecution:
    execution_id: str
    input_sha256: str
    affinity: ExecutionAffinity

    def __post_init__(self):
        require_identifier(self.execution_id, "execution_id")
        require_digest(self.input_sha256, "input_sha256")
        if type(self.affinity) is not ExecutionAffinity:
            raise TypeError("Explicit execution affinity required.")


@runtime_checkable
class IncidentExecutionStore(Protocol):
    @property
    def execution_affinity(self) -> ExecutionAffinity: ...

    def admit(self, *, execution_id: str, input_sha256: str) -> IncidentExecution:
        """Commit an immutable assignment; exact repetition only is idempotent."""
        ...

    def get_execution(self, execution_id: str) -> IncidentExecution:
        """Resolve within this installation/release, never adopt a foreign record."""
        ...

    def uses_approval_store(self, store: object) -> bool:
        """Validate the co-located correlation/consumption store at composition."""
        ...
