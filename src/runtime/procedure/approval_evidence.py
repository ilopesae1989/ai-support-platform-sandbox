from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from .approval_channel import (
    ApprovalDecision,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class ApprovalDecisionEvidence(
    BaseModel
):
    """
    Evidencia inmutable de una decisión HITL
    aceptada por el backend.

    Es independiente del canal concreto.

    Describe:

        quién decidió;
        desde qué canal;
        bajo qué política;
        qué approval_id;
        cuándo.

    NO contiene autoridad operacional.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    workflow_id: str
    approval_id: str

    decision: ApprovalDecision

    channel: str

    identity_scheme: str

    tenant_id: str
    principal_id: str

    channel_user_id: str | None = None

    conversation_id: str | None = None

    authorization_policy_id: str

    display_name: str | None = None

    decided_at: datetime = (
        datetime.min.replace(
            tzinfo=timezone.utc
        )
    )

    @field_validator(
        "workflow_id",
        "approval_id",
        "channel",
        "identity_scheme",
        "tenant_id",
        "principal_id",
        "authorization_policy_id",
    )
    @classmethod
    def validate_exact_required_string(
        cls,
        value: str,
    ) -> str:
        if (
            not isinstance(
                value,
                str,
            )
            or not value
            or not value.strip()
            or value != value.strip()
        ):
            raise ValueError(
                "Los campos de identidad de "
                "ApprovalDecisionEvidence deben "
                "ser strings exactos no vacíos."
            )

        return value

    @field_validator(
        "decided_at",
        mode="before",
    )
    @classmethod
    def default_decided_at(
        cls,
        value,
    ):
        if (
            value is None
            or value
            == datetime.min.replace(
                tzinfo=timezone.utc
            )
        ):
            return utc_now()

        return value

    @field_validator(
        "decided_at"
    )
    @classmethod
    def validate_utc_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo
            is None
        ):
            raise ValueError(
                "decided_at debe incluir timezone."
            )

        return value.astimezone(
            timezone.utc
        )
