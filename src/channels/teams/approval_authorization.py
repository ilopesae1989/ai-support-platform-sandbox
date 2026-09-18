from __future__ import annotations

from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
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
    pass


def _require_exact_string(
    *,
    name: str,
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
            f"{name} debe ser un string "
            "exacto no vacío."
        )

    return value


def _require_canonical_uuid(
    *,
    name: str,
    value: str,
) -> str:
    value = _require_exact_string(
        name=name,
        value=value,
    )

    try:
        parsed = UUID(
            value
        )
    except (
        ValueError,
        TypeError,
        AttributeError,
    ):
        raise ValueError(
            f"{name} debe ser un UUID canónico."
        ) from None

    if str(parsed) != value:
        raise ValueError(
            f"{name} debe usar representación "
            "UUID canónica."
        )

    return value


class ExactTeamsApprovalPolicy(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    policy_id: str

    tenant_id: str

    authorization_directory_tenant_id: str | None = None

    authorized_technicians_group_object_id: str

    @field_validator(
        "policy_id",
        "tenant_id",
    )
    @classmethod
    def validate_exact_string(
        cls,
        value: str,
        info,
    ) -> str:
        return _require_exact_string(
            name=info.field_name,
            value=value,
        )

    @field_validator(
        "authorization_directory_tenant_id"
    )
    @classmethod
    def validate_authorization_directory_tenant_id(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        return _require_exact_string(
            name="authorization_directory_tenant_id",
            value=value,
        )

    @field_validator(
        "authorized_technicians_group_object_id"
    )
    @classmethod
    def validate_group_object_id(
        cls,
        value: str,
    ) -> str:
        return _require_canonical_uuid(
            name=(
                "authorized_technicians_"
                "group_object_id"
            ),
            value=value,
        )


class AuthorizedTeamsApprovalInvocation(
    BaseModel
):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    policy_id: str

    operator: TeamsOperatorIdentity

    action: ApprovalChannelAction


async def authorize_teams_approval_invocation(
    *,
    invocation: TeamsApprovalInvocation,
    policy: ExactTeamsApprovalPolicy,
    membership_checker: object,
    operator_identity_resolver: object | None = None,
) -> AuthorizedTeamsApprovalInvocation:
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

    if (
        invocation.operator.tenant_id
        != policy.tenant_id
    ):
        raise TeamsApprovalAuthorizationError(
            "El operador Teams no está "
            "autorizado para decisiones HITL."
        )

    authorization_directory_tenant_id = (
        policy.authorization_directory_tenant_id
        if policy.authorization_directory_tenant_id
        is not None
        else policy.tenant_id
    )

    authorization_user_object_id = (
        invocation.operator.aad_object_id
    )

    if (
        authorization_directory_tenant_id
        != invocation.operator.tenant_id
    ):
        resolver_method = getattr(
            operator_identity_resolver,
            "resolve_authorization_user_object_id",
            None,
        )

        if not callable(
            resolver_method
        ):
            raise TeamsApprovalAuthorizationError(
                "No existe una autoridad válida "
                "de correlación de identidad."
            )

        try:
            authorization_user_object_id = await (
                resolver_method(
                    source_tenant_id=(
                        invocation.operator.tenant_id
                    ),
                    source_user_object_id=(
                        invocation.operator.aad_object_id
                    ),
                    target_tenant_id=(
                        authorization_directory_tenant_id
                    ),
                )
            )

            authorization_user_object_id = (
                _require_canonical_uuid(
                    name="authorization_user_object_id",
                    value=(
                        authorization_user_object_id
                    ),
                )
            )

        except Exception:
            raise TeamsApprovalAuthorizationError(
                "No pudo demostrarse la correlación "
                "exacta de identidad del operador."
            ) from None

    membership_method = getattr(
        membership_checker,
        "is_transitive_member",
        None,
    )

    if not callable(
        membership_method
    ):
        raise TeamsApprovalAuthorizationError(
            "No existe una autoridad válida "
            "de membership."
        )

    try:
        is_member = await membership_method(
            user_object_id=(
                authorization_user_object_id
            ),
            group_object_id=(
                policy
                .authorized_technicians_group_object_id
            ),
        )
    except Exception:
        raise TeamsApprovalAuthorizationError(
            "No pudo demostrarse la "
            "autorización del operador Teams."
        ) from None

    if is_member is not True:
        raise TeamsApprovalAuthorizationError(
            "El operador Teams no está "
            "autorizado para decisiones HITL."
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
