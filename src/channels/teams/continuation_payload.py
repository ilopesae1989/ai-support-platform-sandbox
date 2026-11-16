"""Teams identity schema selected by the trusted composition root."""
from src.runtime.incident_continuation_codec import ContinuationPayloadCodec

from .approval_authorization import AuthorizedTeamsApprovalInvocation

TEAMS_CONTINUATION_CODEC = ContinuationPayloadCodec(
    invocation_type=AuthorizedTeamsApprovalInvocation,
)
