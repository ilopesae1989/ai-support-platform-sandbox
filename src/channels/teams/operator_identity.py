from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)


class TeamsOperatorIdentity(
    BaseModel
):
    """
    Identidad del operador obtenida exclusivamente
    del contexto autenticado de Microsoft Teams.

    Este objeto NO procede del payload Action.Execute.

    No contiene autoridad operacional.

    Se utilizará posteriormente para:

    - auditoría de la decisión HITL;
    - autorización del aprobador;
    - evidencia de quién aprobó o rechazó.

    Nunca determina:

    - procedure;
    - capability;
    - operation_action;
    - target_resource;
    - parámetros operacionales.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    tenant_id: str

    aad_object_id: str

    teams_user_id: str

    conversation_id: str

    display_name: str | None = None

    @field_validator(
        "tenant_id",
        "aad_object_id",
        "teams_user_id",
        "conversation_id",
    )
    @classmethod
    def validate_required_identity(
        cls,
        value: str,
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                "La identidad Teams debe ser string."
            )

        if not value:
            raise ValueError(
                "La identidad Teams no puede "
                "estar vacía."
            )

        if not value.strip():
            raise ValueError(
                "La identidad Teams no puede "
                "contener únicamente espacios."
            )

        if value != value.strip():
            raise ValueError(
                "La identidad Teams no puede "
                "contener espacios al inicio "
                "o al final."
            )

        return value

    @field_validator(
        "display_name"
    )
    @classmethod
    def validate_display_name(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        if not value.strip():
            return None

        return value.strip()