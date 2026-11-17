"""Teams input adapter for the channel-independent incident HITL processor."""
from typing import Any

from src.runtime.incident_approval_processor import (
    IncidentApprovalProcessingError,
    IncidentApprovalProcessingResult as TeamsIncidentApprovalProcessingResult,
    process_authorized_incident_approval,
)
from src.runtime.procedure.approval_store import PendingApprovalStore

from .approval_authorization import AuthorizedTeamsApprovalInvocation
from .approval_context import to_authorized_approval_context


async def process_authorized_teams_incident_approval(
    *, invocation: AuthorizedTeamsApprovalInvocation, store: PendingApprovalStore,
    workflow: Any, checkpoint_storage: Any,
) -> TeamsIncidentApprovalProcessingResult:
    return await process_authorized_incident_approval(
        invocation=to_authorized_approval_context(invocation),
        store=store, workflow=workflow, checkpoint_storage=checkpoint_storage,
    )
