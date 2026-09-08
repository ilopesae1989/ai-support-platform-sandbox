from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID


_PROJECT_ENDPOINT_NAME = (
    "FOUNDRY_PROJECT_ENDPOINT"
)

_MANAGED_IDENTITY_CLIENT_ID_NAME = (
    "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID"
)


def _required_exact_string(
    *,
    environment: Mapping,
    name: str,
) -> str:
    value = environment.get(
        name
    )

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
            f"{name} debe existir y contener "
            "un valor exacto no vacío."
        )

    return value


def _canonical_client_id(
    value: object,
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
            "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID "
            "debe ser un UUID canónico exacto."
        )

    try:
        parsed = UUID(
            value
        )

    except (
        TypeError,
        ValueError,
        AttributeError,
    ):
        raise ValueError(
            "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID "
            "debe ser un UUID canónico exacto."
        ) from None

    if str(parsed) != value:
        raise ValueError(
            "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID "
            "debe usar representación UUID canónica."
        )

    return value


@dataclass(
    frozen=True
)
class FoundryProductionSettings:
    project_endpoint: str
    managed_identity_client_id: str | None = None


def build_foundry_production_settings(
    environment,
) -> FoundryProductionSettings:
    if not isinstance(
        environment,
        Mapping,
    ):
        raise TypeError(
            "environment debe implementar Mapping."
        )

    project_endpoint = (
        _required_exact_string(
            environment=environment,
            name=_PROJECT_ENDPOINT_NAME,
        )
    )

    managed_identity_client_id = None

    if (
        _MANAGED_IDENTITY_CLIENT_ID_NAME
        in environment
    ):
        managed_identity_client_id = (
            _canonical_client_id(
                environment[
                    _MANAGED_IDENTITY_CLIENT_ID_NAME
                ]
            )
        )

    return FoundryProductionSettings(
        project_endpoint=project_endpoint,
        managed_identity_client_id=(
            managed_identity_client_id
        ),
    )