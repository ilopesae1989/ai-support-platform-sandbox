"""Teams adapters for the canonical runtime evidence contract."""
from src.runtime.procedure.approval_evidence import (
    ApprovalDecisionEvidence,
    ApprovalEvidenceError as TeamsApprovalEvidenceError,
    build_approval_evidence,
    build_approval_evidence_from_request,
    utc_now,
)
from src.runtime.procedure.models import ApprovedProcedureStep
from src.runtime.procedure.workflow import ApprovalOutcome, ApprovalRequest

from .approval_authorization import AuthorizedTeamsApprovalInvocation
from .approval_context import to_authorized_approval_context


def build_teams_approval_evidence(
    *, invocation: AuthorizedTeamsApprovalInvocation,
    workflow_result: ApprovedProcedureStep | ApprovalOutcome,
) -> ApprovalDecisionEvidence:
    return build_approval_evidence(
        invocation=to_authorized_approval_context(invocation),
        workflow_result=workflow_result,
    )


def build_teams_approval_evidence_from_request(
    *, invocation: AuthorizedTeamsApprovalInvocation, request: ApprovalRequest,
) -> ApprovalDecisionEvidence:
    return build_approval_evidence_from_request(
        invocation=to_authorized_approval_context(invocation), request=request,
    )
