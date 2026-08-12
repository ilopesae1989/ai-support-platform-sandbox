from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .operational_context import (
    OperationalContext,
)


class ResourceIdentityResolutionError(
    ValueError
):
    """
    La identidad operacional de un recurso no puede
    resolverse de forma determinista y segura.
    """

    pass


@dataclass(
    frozen=True
)
class ResolvedResourceIdentity:
    """
    Identidad operacional autoritativa resuelta por
    Python.

    canonical_target_resource:
        identidad que entra en Runtime/HITL.

    allowed_cognitive_targets:
        representaciones que Procedure puede haber
        utilizado para referirse al MISMO recurso.

    Esas representaciones no adquieren autoridad.
    Sólo sirven para comprobar que el resultado
    cognitivo no contradice el contexto autoritativo.
    """

    operation_domain: str

    resource_type: str

    canonical_target_resource: str

    required_parameters: tuple[
        str,
        ...
    ]

    allowed_cognitive_targets: tuple[
        str,
        ...
    ]

    def validate_cognitive_target(
        self,
        target_resource: str | None,
    ) -> None:
        """
        Comprueba que el target expresado por Procedure
        representa exactamente el mismo recurso que la
        identidad construida por Python.

        No normaliza.
        No hace fuzzy matching.
        No intenta corregir el resultado del agente.
        """

        if (
            target_resource
            not in self.allowed_cognitive_targets
        ):
            raise (
                ResourceIdentityResolutionError(
                    "target_resource cognitivo "
                    "no corresponde con la "
                    "identidad operacional "
                    "autoritativa. "
                    "target_resource="
                    f"{target_resource!r}; "
                    "valores admitidos="
                    f"{self.allowed_cognitive_targets!r}."
                )
            )


class ResourceIdentityResolver(
    Protocol
):
    """
    Contrato que debe implementar cualquier resolver
    de identidad de recurso.

    Runtime no necesita conocer VMs, Storage,
    SQL, Windows, Linux, etc.

    Sólo conoce este contrato.
    """

    operation_domain: str

    resource_type: str

    required_parameters: tuple[
        str,
        ...
    ]

    def resolve(
        self,
        context: OperationalContext,
    ) -> ResolvedResourceIdentity:
        """
        Construye identidad exclusivamente desde
        OperationalContext tipado/autoritativo.
        """

        ...