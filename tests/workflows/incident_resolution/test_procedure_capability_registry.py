from dataclasses import (
    FrozenInstanceError,
)

import pytest

from src.workflows.incident_resolution.capability_registry import (
    CapabilityNotFoundError,
    build_default_capability_registry,
)

from src.workflows.incident_resolution.procedure_capability_binding import (
    ProcedureCapabilityBinding,
    ProcedureCapabilityBindingError,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    DuplicateProcedureCapabilityBindingError,
    ProcedureCapabilityBindingNotFoundError,
    ProcedureCapabilityRegistry,
)


PROCEDURE_A = (
    "TEST-PROC-VM-A"
)

PROCEDURE_B = (
    "TEST-PROC-VM-B"
)

VERSION = (
    "1.0"
)

STEP_ID = (
    "2"
)


def create_registry(
):
    capability_registry = (
        build_default_capability_registry()
    )

    return ProcedureCapabilityRegistry(
        capability_registry=(
            capability_registry
        ),

        bindings=[
            ProcedureCapabilityBinding(
                procedure_id=(
                    PROCEDURE_A
                ),

                procedure_version=(
                    VERSION
                ),

                step_id=(
                    STEP_ID
                ),

                capability_id=(
                    "azure.vm.start"
                ),
            ),
        ],
    )


def test_exact_procedure_step_resolves_capability():
    registry = create_registry()

    capability = (
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),
        )
    )

    assert (
        capability.capability_id
        == "azure.vm.start"
    )


def test_version_mismatch_fails_closed():
    registry = create_registry()

    with pytest.raises(
        ProcedureCapabilityBindingNotFoundError,
    ):
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version=(
                "2.0"
            ),

            step_id=(
                STEP_ID
            ),
        )


def test_step_mismatch_fails_closed():
    registry = create_registry()

    with pytest.raises(
        ProcedureCapabilityBindingNotFoundError,
    ):
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version=(
                VERSION
            ),

            step_id="99",
        )


def test_procedure_id_is_not_normalized():
    registry = create_registry()

    with pytest.raises(
        ProcedureCapabilityBindingNotFoundError,
    ):
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_A.lower()
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),
        )


def test_duplicate_exact_binding_is_rejected():
    capability_registry = (
        build_default_capability_registry()
    )

    first = (
        ProcedureCapabilityBinding(
            procedure_id=PROCEDURE_A,
            procedure_version=VERSION,
            step_id=STEP_ID,
            capability_id=(
                "azure.vm.start"
            ),
        )
    )

    second = (
        ProcedureCapabilityBinding(
            procedure_id=PROCEDURE_A,
            procedure_version=VERSION,
            step_id=STEP_ID,
            capability_id=(
                "azure.vm.start"
            ),
        )
    )

    with pytest.raises(
        DuplicateProcedureCapabilityBindingError,
    ):
        ProcedureCapabilityRegistry(
            capability_registry=(
                capability_registry
            ),

            bindings=[
                first,
                second,
            ],
        )


def test_binding_to_unknown_capability_is_rejected():
    capability_registry = (
        build_default_capability_registry()
    )

    with pytest.raises(
        CapabilityNotFoundError,
    ):
        ProcedureCapabilityRegistry(
            capability_registry=(
                capability_registry
            ),

            bindings=[
                ProcedureCapabilityBinding(
                    procedure_id=(
                        PROCEDURE_A
                    ),

                    procedure_version=(
                        VERSION
                    ),

                    step_id=(
                        STEP_ID
                    ),

                    capability_id=(
                        "azure.vm.restart"
                    ),
                ),
            ],
        )


def test_binding_is_immutable():
    binding = (
        ProcedureCapabilityBinding(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version=(
                VERSION
            ),

            step_id=(
                STEP_ID
            ),

            capability_id=(
                "azure.vm.start"
            ),
        )
    )

    with pytest.raises(
        FrozenInstanceError,
    ):
        binding.step_id = "99"


def test_binding_requires_exact_nonempty_version():
    with pytest.raises(
        ProcedureCapabilityBindingError,
        match="procedure_version",
    ):
        ProcedureCapabilityBinding(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version="",

            step_id=(
                STEP_ID
            ),

            capability_id=(
                "azure.vm.start"
            ),
        )
def test_different_procedures_can_reuse_same_capability():
    """
    Dos procedimientos distintos pueden reutilizar
    exactamente la misma capability operacional.

    La unidad de crecimiento de la plataforma es la
    capability, no la alerta ni el procedimiento.
    """

    capability_registry = (
        build_default_capability_registry()
    )

    registry = (
        ProcedureCapabilityRegistry(
            capability_registry=(
                capability_registry
            ),

            bindings=[
                ProcedureCapabilityBinding(
                    procedure_id=(
                        PROCEDURE_A
                    ),

                    procedure_version=(
                        VERSION
                    ),

                    step_id="2",

                    capability_id=(
                        "azure.vm.start"
                    ),
                ),

                ProcedureCapabilityBinding(
                    procedure_id=(
                        PROCEDURE_B
                    ),

                    procedure_version=(
                        VERSION
                    ),

                    step_id="5",

                    capability_id=(
                        "azure.vm.start"
                    ),
                ),
            ],
        )
    )

    first = (
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_A
            ),

            procedure_version=(
                VERSION
            ),

            step_id="2",
        )
    )

    second = (
        registry.resolve_capability(
            procedure_id=(
                PROCEDURE_B
            ),

            procedure_version=(
                VERSION
            ),

            step_id="5",
        )
    )

    assert (
        first.capability_id
        == "azure.vm.start"
    )

    assert (
        second.capability_id
        == "azure.vm.start"
    )

    #
    # El catálogo devuelve la misma capability
    # instalada, no dos copias específicas para
    # cada procedimiento.
    #
    assert first is second