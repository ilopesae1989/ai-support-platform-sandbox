"""Common data contract after a channel has authenticated and authorized HITL.

Inheritance is not proof of authorization. Only trusted adapters construct these
records; the pending store and checkpoint still govern operational authority.
Concrete channel models retain their own authenticated identity fields.
"""
from pydantic import BaseModel, ConfigDict

from src.runtime.procedure.approval_channel import ApprovalChannelAction


class AuthorizedApprovalInvocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_id: str
    action: ApprovalChannelAction
