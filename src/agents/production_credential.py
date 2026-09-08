from __future__ import annotations

from azure.identity import (
    ManagedIdentityCredential,
)

from src.agents.production_settings import (
    FoundryProductionSettings,
)


def build_foundry_production_credential(
    settings,
) -> ManagedIdentityCredential:
    if not isinstance(
        settings,
        FoundryProductionSettings,
    ):
        raise TypeError(
            "settings debe ser "
            "FoundryProductionSettings."
        )

    client_id = (
        settings.managed_identity_client_id
    )

    if client_id is None:
        return ManagedIdentityCredential()

    return ManagedIdentityCredential(
        client_id=client_id
    )