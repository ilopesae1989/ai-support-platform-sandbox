from __future__ import annotations

from collections.abc import (
    Iterable,
)

from .capability_registry import (
    CapabilityRegistry,
    build_default_capability_registry,
)

from .operational_capability import (
    OperationalCapability,
)

from .procedure_capability_binding import (
    ProcedureCapabilityBinding,
)


class ProcedureCapabilityRegistryError(
    ValueError
):
    pass


class ProcedureCapabilityBindingNotFoundError(
    ProcedureCapabilityRegistryError
):
    pass


class DuplicateProcedureCapabilityBindingError(
    ProcedureCapabilityRegistryError
):
    pass


class ProcedureCapabilityRegistry:
    """
    Registro determinista:

        procedure_id
        procedure_version
        step_id
            ↓
        capability_id

    No existe:

    - fuzzy matching;
    - aliases;
    - wildcard de versión;
    - fallback a otro step;
    - selección mediante LLM.
    """

    def __init__(
        self,
        *,
        capability_registry: CapabilityRegistry,

        bindings: Iterable[
            ProcedureCapabilityBinding
        ],
    ) -> None:

        self._capability_registry = (
            capability_registry
        )

        self._bindings: dict[
            tuple[
                str,
                str,
                str,
            ],
            ProcedureCapabilityBinding,
        ] = {}

        for binding in bindings:
            self.register(
                binding
            )

    def register(
        self,
        binding: ProcedureCapabilityBinding,
    ) -> None:

        if not isinstance(
            binding,
            ProcedureCapabilityBinding,
        ):
            raise (
                ProcedureCapabilityRegistryError(
                    "Sólo pueden registrarse "
                    "ProcedureCapabilityBinding."
                )
            )

        #
        # Una capability inexistente nunca puede
        # adquirir autoridad mediante un binding.
        #
        self._capability_registry.get(
            binding.capability_id
        )

        key = (
            binding.procedure_id,
            binding.procedure_version,
            binding.step_id,
        )

        if key in self._bindings:
            raise (
                DuplicateProcedureCapabilityBindingError(
                    "Ya existe un binding para "
                    "procedure_id="
                    f"{binding.procedure_id!r}, "
                    "procedure_version="
                    f"{binding.procedure_version!r}, "
                    "step_id="
                    f"{binding.step_id!r}."
                )
            )

        self._bindings[
            key
        ] = binding

    def get_binding(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> ProcedureCapabilityBinding:

        key = (
            procedure_id,
            procedure_version,
            step_id,
        )

        binding = (
            self._bindings.get(
                key
            )
        )

        if binding is None:
            raise (
                ProcedureCapabilityBindingNotFoundError(
                    "No existe capability binding "
                    "para procedure_id="
                    f"{procedure_id!r}, "
                    "procedure_version="
                    f"{procedure_version!r}, "
                    "step_id="
                    f"{step_id!r}."
                )
            )

        return binding

    def resolve_capability(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> OperationalCapability:

        binding = self.get_binding(
            procedure_id=procedure_id,
            procedure_version=(
                procedure_version
            ),
            step_id=step_id,
        )

        return (
            self._capability_registry
            .get(
                binding.capability_id
            )
        )

    def contains_binding(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        step_id: str,
    ) -> bool:
        """
        Comprueba exclusivamente la existencia del
        binding exacto.

        No aplica:

        - aliases;
        - fuzzy matching;
        - fallback de versión;
        - fallback de step.
        """

        return (
            (
                procedure_id,
                procedure_version,
                step_id,
            )
            in self._bindings
        )

    def count(
        self,
    ) -> int:
        return len(
            self._bindings
        )


def build_default_procedure_capability_registry(
) -> ProcedureCapabilityRegistry:
    """
    Construye el registry gobernado de bindings
    actualmente publicados.

    Los bindings representan exclusivamente
    procedimientos corporativos reales y versionados.

    La resolución es exacta:

        procedure_id
        procedure_version
        step_id
            ↓
        capability_id

    Dos procedimientos distintos pueden reutilizar
    una misma capability operacional.

    No existe:

    - fuzzy matching;
    - aliases;
    - wildcard de versión;
    - fallback de step;
    - inferencia desde operation_action;
    - selección mediante LLM.
    """

    return ProcedureCapabilityRegistry(
        capability_registry=(
            build_default_capability_registry()
        ),

        bindings=[
            ProcedureCapabilityBinding(
                procedure_id=(
                    "NTTSY-SBX-AZ-VM-001"
                ),

                procedure_version=(
                    "1.0"
                ),

                step_id=(
                    "1"
                ),

                capability_id=(
                    "azure.vm.start"
                ),
            ),

            ProcedureCapabilityBinding(
                procedure_id=(
                    "NTTSY-SBX-AZ-VM-002"
                ),

                procedure_version=(
                    "1.0"
                ),

                step_id=(
                    "1"
                ),

                capability_id=(
                    "azure.vm.start"
                ),
            ),
        ],
    )