from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


class AuthorizationIdentityResolutionError(
    RuntimeError
):
    pass


def _canonical_uuid(
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
        raise AuthorizationIdentityResolutionError(
            f"{name} inválido."
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
        raise AuthorizationIdentityResolutionError(
            f"{name} inválido."
        ) from None

    if str(parsed) != value:
        raise AuthorizationIdentityResolutionError(
            f"{name} inválido."
        )

    return value


@dataclass(
    frozen=True
)
class ExactTeamsAuthorizationIdentityMapping:
    source_tenant_id: str
    source_user_object_id: str
    target_tenant_id: str
    target_user_object_id: str

    def __post_init__(
        self,
    ) -> None:
        _canonical_uuid(
            name="source_tenant_id",
            value=self.source_tenant_id,
        )

        _canonical_uuid(
            name="source_user_object_id",
            value=self.source_user_object_id,
        )

        _canonical_uuid(
            name="target_tenant_id",
            value=self.target_tenant_id,
        )

        _canonical_uuid(
            name="target_user_object_id",
            value=self.target_user_object_id,
        )


class ExactTeamsAuthorizationObjectIdResolver:
    def __init__(
        self,
        *,
        mappings,
    ):
        self._mappings = {}

        for mapping in mappings:
            if not isinstance(
                mapping,
                ExactTeamsAuthorizationIdentityMapping,
            ):
                raise TypeError(
                    "mappings debe contener únicamente "
                    "ExactTeamsAuthorizationIdentityMapping."
                )

            key = (
                mapping.source_tenant_id,
                mapping.source_user_object_id,
                mapping.target_tenant_id,
            )

            if key in self._mappings:
                raise AuthorizationIdentityResolutionError(
                    "Existe una correlación de identidad duplicada."
                )

            self._mappings[
                key
            ] = mapping.target_user_object_id

    async def resolve_authorization_user_object_id(
        self,
        *,
        source_tenant_id: str,
        source_user_object_id: str,
        target_tenant_id: str,
    ) -> str:
        key = (
            _canonical_uuid(
                name="source_tenant_id",
                value=source_tenant_id,
            ),
            _canonical_uuid(
                name="source_user_object_id",
                value=source_user_object_id,
            ),
            _canonical_uuid(
                name="target_tenant_id",
                value=target_tenant_id,
            ),
        )

        try:
            resolved = self._mappings[
                key
            ]
        except KeyError:
            raise AuthorizationIdentityResolutionError(
                "No existe una correlación exacta "
                "de identidad autorizada."
            ) from None

        return _canonical_uuid(
            name="target_user_object_id",
            value=resolved,
        )


def build_exact_teams_authorization_object_id_resolver(
    *,
    mappings,
) -> ExactTeamsAuthorizationObjectIdResolver:
    return ExactTeamsAuthorizationObjectIdResolver(
        mappings=mappings
    )
