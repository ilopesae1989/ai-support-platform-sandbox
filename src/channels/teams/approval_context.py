"""Map authenticated Teams identity after the existing authorization boundary."""
from src.runtime.procedure.approval_context import ApprovalIdentity, AuthorizedApprovalContext

from .approval_authorization import AuthorizedTeamsApprovalInvocation


def to_authorized_approval_context(
    invocation: AuthorizedTeamsApprovalInvocation,
) -> AuthorizedApprovalContext:
    if not isinstance(invocation, AuthorizedTeamsApprovalInvocation):
        raise TypeError("invocation debe ser AuthorizedTeamsApprovalInvocation.")
    return AuthorizedApprovalContext(
        policy_id=invocation.policy_id,
        action=invocation.action,
        identity=ApprovalIdentity(
            channel="msteams",
            identity_scheme="microsoft_entra_object_id",
            tenant_id=invocation.operator.tenant_id,
            principal_id=invocation.operator.aad_object_id,
            conversation_id=invocation.operator.conversation_id,
            channel_user_id=invocation.operator.teams_user_id,
            display_name=invocation.operator.display_name,
        ),
    )
