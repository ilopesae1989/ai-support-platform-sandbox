"""Teams input adapter for the original approval-only workflow."""
from typing import Any

from src.runtime.procedure.approval_processor import (
    ApprovalProcessingResult as TeamsApprovalProcessingResult,
    process_authorized_approval,
)
from src.runtime.procedure.approval_store import PendingApprovalStore

from .approval_authorization import AuthorizedTeamsApprovalInvocation
from .approval_context import to_authorized_approval_context


async def process_authorized_teams_approval(
    *, invocation: AuthorizedTeamsApprovalInvocation, store: PendingApprovalStore, workflow: Any,
) -> TeamsApprovalProcessingResult:
    return await process_authorized_approval(
        invocation=to_authorized_approval_context(invocation), store=store, workflow=workflow,
    )
