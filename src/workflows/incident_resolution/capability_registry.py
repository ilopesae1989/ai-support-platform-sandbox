from __future__ import annotations

from collections.abc import (
    Iterable,
)

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from .operational_capability import (
    OperationalCapability,
)


class CapabilityRegistryError(
    ValueError
):
    pass


class CapabilityNotFoundError(
    CapabilityRegistryError
):
    pass


class DuplicateCapabilityError(
    CapabilityRegistryError
):
    pass


class DuplicateCapabilitySignatureError(
    CapabilityRegistryError
):
    pass


class CapabilityRegistry:
    """
    Catálogo determinista de capacidades
    operacionales instaladas.

    La selección es exacta.

    No existe:

    - fuzzy matching;
    - aliases;
    - normalización;
    - fallback;
    - selección mediante LLM.
    """

    def __init__(
        self,
        *,
        capabilities: Iterable[
            OperationalCapability
        ],
    ) -> None:

        self._capabilities: dict[
            str,
            OperationalCapability,
        ] = {}

        self._signatures: set[
            tuple[
                str,
                str,
                OperationKind,
                OperationAction,
            ]
        ] = set()

        for capability in capabilities:
            self.register(
                capability
            )

    def register(
        self,
        capability: OperationalCapability,
    ) -> None:

        if not isinstance(
            capability,
            OperationalCapability,
        ):
            raise CapabilityRegistryError(
                "Sólo pueden registrarse "
                "instancias de "
                "OperationalCapability."
            )

        if (
            capability.capability_id
            in self._capabilities
        ):
            raise DuplicateCapabilityError(
                "capability_id ya registrado: "
                f"{capability.capability_id!r}."
            )

        signature = (
            capability.operation_domain,
            capability.resource_type,
            capability.operation_kind,
            capability.operation_action,
        )

        if signature in self._signatures:
            raise (
                DuplicateCapabilitySignatureError(
                    "Ya existe una capability "
                    "para la misma firma operacional: "
                    f"{signature!r}."
                )
            )

        self._capabilities[
            capability.capability_id
        ] = capability

        self._signatures.add(
            signature
        )

    def get(
        self,
        capability_id: str,
    ) -> OperationalCapability:

        capability = (
            self._capabilities.get(
                capability_id
            )
        )

        if capability is None:
            raise CapabilityNotFoundError(
                "Capability no registrada: "
                f"{capability_id!r}."
            )

        return capability

    def contains(
        self,
        capability_id: str,
    ) -> bool:
        return (
            capability_id
            in self._capabilities
        )

    def count(
        self,
    ) -> int:
        return len(
            self._capabilities
        )


def build_default_capability_registry(
) -> CapabilityRegistry:
    """
    Capacidades operacionales instaladas actualmente.

    Registrar una capability aquí NO significa
    que cualquier procedimiento pueda utilizarla.

    Ese binding se gobierna por separado.
    """

    return CapabilityRegistry(
        capabilities=[
            OperationalCapability(
                capability_id=(
                    "azure.vm.start"
                ),

                operation_domain=(
                    "azure"
                ),

                resource_type=(
                    "Microsoft.Compute/"
                    "virtualMachines"
                ),

                operation_kind=(
                    OperationKind.WRITE
                ),

                operation_action=(
                    OperationAction.VM_START
                ),

                required_parameters=(
                    "subscription_id",
                    "resource_group",
                    "vm_name",
                ),

                hitl_required=True,

                executor_id=(
                    "azure_operations"
                ),
            ),
        ]
    )