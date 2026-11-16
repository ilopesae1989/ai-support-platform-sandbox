"""Explicit, host-selected payload type for trusted continuation persistence.

The payload never selects a Python type or grants authorization. JSON encoding
matches the historical Teams writer; there is no new envelope or SQL migration.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Generic, TypeVar

from src.runtime.procedure.authorized_approval import AuthorizedApprovalInvocation

InvocationT = TypeVar("InvocationT", bound=AuthorizedApprovalInvocation)


@dataclass(frozen=True, kw_only=True)
class ContinuationPayloadCodec(Generic[InvocationT]):
    invocation_type: type[InvocationT]

    def __post_init__(self) -> None:
        if not isinstance(self.invocation_type, type) or not issubclass(
            self.invocation_type, AuthorizedApprovalInvocation
        ):
            raise TypeError("An explicit authorized invocation model is required.")

    def encode(self, invocation: InvocationT) -> str:
        if not isinstance(invocation, self.invocation_type):
            raise TypeError(f"invocation must be {self.invocation_type.__name__}.")
        return json.dumps(
            invocation.model_dump(mode="json"),
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )

    def decode(self, payload: str) -> InvocationT:
        return self.invocation_type.model_validate(json.loads(payload))
