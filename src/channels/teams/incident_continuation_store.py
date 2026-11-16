"""Compatibility imports and the local Teams store adapter.

Lifecycle and persistence live outside the channel. This adapter only selects
its authenticated identity schema; existing callers retain their constructor.
"""
from pathlib import Path

from src.runtime.incident_continuation_store import (
    IncidentContinuationClaimError, IncidentContinuationConflictError,
    IncidentContinuationJob, IncidentContinuationStatus, IncidentContinuationStore,
)
from src.persistence.sqlite.incident_continuation_store import (
    SqliteIncidentContinuationStore as _SqliteIncidentContinuationStore,
)
from .continuation_payload import TEAMS_CONTINUATION_CODEC


class SqliteIncidentContinuationStore(_SqliteIncidentContinuationStore):
    def __init__(self, database_path: str | Path) -> None:
        super().__init__(database_path, payload_codec=TEAMS_CONTINUATION_CODEC)
