from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from .approval_invocation import (
    TeamsApprovalInvocation,
)

from .operator_identity import (
    TeamsOperatorIdentity,
)

from src.runtime.procedure.approval_channel import (
    ApprovalChannelAction,
)


class TeamsApprovalAuthorizationError(
    PermissionError
):
    """
    El operador Teams está identificado, pero
    no está autorizado para aprobar/rechazar
    operaciones HITL.
    """

    pass


class TeamsApprovalPrincipal(
    BaseModel
):
    """
    Principal exacto autorizado para HITL.

    La identidad está compuesta por:

        tenant_id
        aad_object_id

    No se autoriza por nombre visible,
    Teams user id ni conversación.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    tenant_id: str
    aad_object_id: str

    @field_validator(
        "tenant_id",
        "aad_object_id",
    )
    @classmethod
    def validate_exact_identity(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                "La identidad autorizada debe "
                "ser string."
            )

        if not value:
            raise ValueError(
                "La identidad autorizada no "
                "puede estar vacía."
            )

        if not value.strip():
            raise ValueError(
                "La identidad autorizada no "
                "puede contener sólo espacios."
            )

        if (
            value
            != value.strip()
        ):
            raise ValueError(
                "La identidad autorizada no "
                "puede contener espacios al "
                "inicio o al final."
            )

        return value


class ExactTeamsApprovalPolicy(
    BaseModel
):
    """
    Política exacta de autorización para el MVP.

    NO existe:

    - allow-all;
    - wildcard;
    - fuzzy matching;
    - autorización por display_name;
    - autorización por teams_user_id;
    - selección mediante LLM.

    La implementación productiva podrá sustituirse
    posteriormente por Microsoft Entra App Roles
    sin modificar el contrato del canal.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    policy_id: str

    allowed_principals: tuple[
        TeamsApprovalPrincipal,
        ...,
    ]

    @field_validator(
        "policy_id"
    )
    @classmethod
    def validate_policy_id(
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
                "policy_id debe ser un string "
                "no vacío y exacto."
            )

        return value

    @model_validator(
        mode="after"
    )
    def validate_principals(
        self,
    ):
        if not self.allowed_principals:
            raise ValueError(
                "La política HITL debe contener "
                "al menos un principal autorizado."
            )

        identities = [
            (
                principal.tenant_id,
                principal.aad_object_id,
            )
            for principal
            in self.allowed_principals
        ]

        if (
            len(identities)
            != len(
                set(
                    identities
                )
            )
        ):
            raise ValueError(
                "La política HITL contiene "
                "principales duplicados."
            )

        return self


class AuthorizedTeamsApprovalInvocation(
    BaseModel
):
    """
    Resultado de superar explícitamente la
    frontera de autorización Teams.

    Sigue sin contener ninguna autoridad
    operacional.

    Sólo certifica que:

        identidad autenticada
            +
        decisión mínima
            +
        policy Python
            ↓
        operador autorizado
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    policy_id: str

    operator: TeamsOperatorIdentity

    action: ApprovalChannelAction


def authorize_teams_approval_invocation(
    *,
    invocation: TeamsApprovalInvocation,
    policy: ExactTeamsApprovalPolicy,
) -> AuthorizedTeamsApprovalInvocation:
    """
    Autoriza mediante coincidencia exacta de:

        tenant_id
        aad_object_id

    El canal no decide la política.

    El usuario no puede proporcionar ni modificar
    la allowlist desde Action.Execute.data.
    """

    if not isinstance(
        invocation,
        TeamsApprovalInvocation,
    ):
        raise TypeError(
            "invocation debe ser "
            "TeamsApprovalInvocation."
        )

    if not isinstance(
        policy,
        ExactTeamsApprovalPolicy,
    ):
        raise TypeError(
            "policy debe ser "
            "ExactTeamsApprovalPolicy."
        )

    identity = (
        invocation.operator.tenant_id,
        invocation.operator.aad_object_id,
    )

    allowed_identities = {
        (
            principal.tenant_id,
            principal.aad_object_id,
        )
        for principal
        in policy.allowed_principals
    }

    if (
        identity
        not in allowed_identities
    ):
        raise (
            TeamsApprovalAuthorizationError(
                "El operador Teams no está "
                "autorizado para realizar "
                "decisiones HITL."
            )
        )

    return AuthorizedTeamsApprovalInvocation(
        policy_id=(
            policy.policy_id
        ),

        operator=(
            invocation.operator
        ),

        action=(
            invocation.action
        ),
    )