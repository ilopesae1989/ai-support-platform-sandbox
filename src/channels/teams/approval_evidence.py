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

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
)

from src.runtime.procedure.workflow import (
    ApprovalOutcome,
)

from .approval_authorization import (
    AuthorizedTeamsApprovalInvocation,
)

from src.runtime.procedure.approval_channel import (
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


class TeamsApprovalEvidenceError(
    ValueError
):
    pass


def build_teams_approval_evidence(
    *,
    invocation: AuthorizedTeamsApprovalInvocation,
    workflow_result: (
        ApprovedProcedureStep
        | ApprovalOutcome
    ),
) -> ApprovalDecisionEvidence:
    """
    Construye evidencia sólo DESPUÉS de que
    Agent Framework haya aceptado la decisión HITL.

    No basta con que Teams haya enviado un click.
    """

    if not isinstance(
        invocation,
        AuthorizedTeamsApprovalInvocation,
    ):
        raise TypeError(
            "invocation debe ser "
            "AuthorizedTeamsApprovalInvocation."
        )

    if (
        workflow_result.workflow_id
        == ""
        or workflow_result.workflow_id
        is None
    ):
        raise TeamsApprovalEvidenceError(
            "El resultado HITL no contiene "
            "workflow_id válido."
        )

    decision = (
        invocation.action.decision
    )

    if (
        decision
        == ApprovalDecision.APPROVE
    ):
        if not isinstance(
            workflow_result,
            ApprovedProcedureStep,
        ):
            raise TeamsApprovalEvidenceError(
                "Una decisión approve debe haber "
                "producido ApprovedProcedureStep."
            )

        if (
            workflow_result.approved
            is not True
        ):
            raise TeamsApprovalEvidenceError(
                "ApprovedProcedureStep no está "
                "marcado como aprobado."
            )

        if (
            workflow_result.approval_id
            != invocation.action.approval_id
        ):
            raise TeamsApprovalEvidenceError(
                "approval_id del resultado no "
                "coincide con la decisión Teams."
            )

    elif (
        decision
        == ApprovalDecision.REJECT
    ):
        if not isinstance(
            workflow_result,
            ApprovalOutcome,
        ):
            raise TeamsApprovalEvidenceError(
                "Una decisión reject debe haber "
                "producido ApprovalOutcome."
            )

        if (
            workflow_result.approved
            is not False
        ):
            raise TeamsApprovalEvidenceError(
                "ApprovalOutcome no representa "
                "un rechazo."
            )

    else:
        raise TeamsApprovalEvidenceError(
            "Decisión HITL no soportada."
        )

    return ApprovalDecisionEvidence(
        workflow_id=(
            workflow_result.workflow_id
        ),

        approval_id=(
            invocation.action.approval_id
        ),

        decision=(
            decision
        ),

        channel=(
            "msteams"
        ),

        identity_scheme=(
            "microsoft_entra_object_id"
        ),

        tenant_id=(
            invocation.operator.tenant_id
        ),

        principal_id=(
            invocation.operator.aad_object_id
        ),

        channel_user_id=(
            invocation.operator.teams_user_id
        ),

        conversation_id=(
            invocation.operator.conversation_id
        ),

        authorization_policy_id=(
            invocation.policy_id
        ),

        display_name=(
            invocation.operator.display_name
        ),

        decided_at=None,
    )