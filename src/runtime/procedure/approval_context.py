"""Trusted channel identity accompanying an already authorized HITL decision.

This is an internal application input, not an authentication mechanism or an
operational capability. Channels must authorize before constructing it.
"""
from pydantic import BaseModel, ConfigDict, field_validator

from .authorized_approval import AuthorizedApprovalInvocation


def _exact(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Approval identity fields must be exact nonempty strings.")
    return value


class ApprovalIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: str
    identity_scheme: str
    tenant_id: str
    principal_id: str
    conversation_id: str
    channel_user_id: str | None = None
    display_name: str | None = None

    @field_validator("channel", "identity_scheme", "tenant_id", "principal_id", "conversation_id")
    @classmethod
    def exact_identity(cls, value: str) -> str:
        return _exact(value)


class AuthorizedApprovalContext(AuthorizedApprovalInvocation):
    identity: ApprovalIdentity

    @field_validator("policy_id")
    @classmethod
    def exact_policy(cls, value: str) -> str:
        return _exact(value)
