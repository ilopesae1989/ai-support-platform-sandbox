import pytest

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from src.workflows.incident_resolution.capability_registry import (
    build_default_capability_registry,
)

from src.workflows.incident_resolution.executors.runtime import (
    ProcedureRuntimeExecutor,
)

from src.workflows.incident_resolution.models import (
    ExecutionIdentity,
    ProcedureExecutionContext,
    ProcedureExecutionRequest,
)

from src.workflows.incident_resolution.operational_context import (
    OperationalContext,
)

from src.workflows.incident_resolution.procedure_capability_binding import (
    ProcedureCapabilityBinding,
)

from src.workflows.incident_resolution.procedure_capability_registry import (
    ProcedureCapabilityRegistry,
)

from src.workflows.incident_resolution.resource_identity_registry import (
    build_default_resource_identity_registry,
)


ALERT_ID = (
    "ALT-VM-START-001"
)

WORKFLOW_ID = (
    "wf-vm-start-001"
)

CORRELATION_ID = (
    "corr-vm-start-001"
)

PROCEDURE_ID = (
    "TEST-PROC-VM-START"
)

PROCEDURE_VERSION = (
    "1.0"
)

STEP_ID = (
    "2"
)

SUBSCRIPTION_ID = (
    "557fdabc-f3b6-4c24-"
    "a9ae-e9e89b5ad172"
)

RESOURCE_GROUP = (
    "rg-icenter-sandbox-vm-demo"
)

VM_NAME = (
    "vm-icenter-sbx-demo-01"
)

VM_RESOURCE_TYPE = (
    "Microsoft.Compute/"
    "virtualMachines"
)

CANONICAL_VM_RESOURCE_ID = (
    "/subscriptions/"
    f"{SUBSCRIPTION_ID}"
    "/resourceGroups/"
    f"{RESOURCE_GROUP}"
    "/providers/Microsoft.Compute/"
    "virtualMachines/"
    f"{VM_NAME}"
)


def create_request(
) -> ProcedureExecutionRequest:
    """
    Request cognitivo previo al Procedure Agent.

    No contiene operation_action ni capability_id.
    """

    return ProcedureExecutionRequest(
        alert_id=(
            ALERT_ID
        ),

        procedure_found=True,

        procedure_match=(
            "exact"
        ),

        execution_eligible=True,

        procedure_id=(
            PROCEDURE_ID
        ),

        procedure_name=(
            "Test VM Start"
        ),

        procedure_version=(
            PROCEDURE_VERSION
        ),

        affected_resource=(
            VM_NAME
        ),

        incident_description=(
            "La máquina virtual requiere "
            "arranque controlado."
        ),
    )


def create_execution_identity(
) -> ExecutionIdentity:
    """
    Identidad de ejecución generada por Python.
    """

    return ExecutionIdentity(
        workflow_id=(
            WORKFLOW_ID
        ),

        alert_id=(
            ALERT_ID
        ),

        correlation_id=(
            CORRELATION_ID
        ),
    )


def create_operational_context(
) -> OperationalContext:
    """
    Identidad operacional autoritativa.

    Estos valores no proceden del LLM.
    """

    return OperationalContext(
        alert_id=(
            ALERT_ID
        ),

        affected_resource=(
            VM_NAME
        ),

        resource_type=(
            VM_RESOURCE_TYPE
        ),

        service=(
            "Azure Virtual Machines"
        ),

        environment=(
            "sandbox"
        ),

        subscription_id=(
            SUBSCRIPTION_ID
        ),

        resource_group=(
            RESOURCE_GROUP
        ),

        vm_name=(
            VM_NAME
        ),

        tenant_id=(
            "0cb40b2b-6cfc-4c63-"
            "bf7b-da710ea390cb"
        ),

        correlation_id=(
            CORRELATION_ID
        ),
    )


def create_procedure_result(
) -> ProcedureExecutionResult:
    """
    Simula exclusivamente la salida cognitiva
    del Procedure Agent.

    El agente interpreta:

        operation_domain = azure
        operation_kind = write
        target_resource = VM_NAME
        required_parameters = [...]

    pero NO declara:

        OperationAction.VM_START
        capability_id = azure.vm.start
    """

    return (
        ProcedureExecutionResult
        .model_validate(
            {
                "alert_id": (
                    ALERT_ID
                ),

                "procedure": {
                    "id": (
                        PROCEDURE_ID
                    ),

                    "name": (
                        "Test VM Start"
                    ),

                    "version": (
                        PROCEDURE_VERSION
                    ),
                },

                "execution_allowed": (
                    True
                ),

                "blocked_by_policy": (
                    False
                ),

                "total_steps": (
                    2
                ),

                "current_step": (
                    2
                ),

                "step": {
                    "id": (
                        STEP_ID
                    ),

                    "description": (
                        "Arrancar la máquina virtual "
                        "autorizada."
                    ),

                    "step_type": (
                        "technical_operation"
                    ),

                    "operation_domain": (
                        "azure"
                    ),

                    "operation_kind": (
                        "write"
                    ),

                    "target_resource": (
                        VM_NAME
                    ),

                    "required_parameters": [
                        "subscription_id",
                        "resource_group",
                        "vm_name",
                    ],

                    "preconditions": [
                        (
                            "La VM debe corresponder "
                            "a la incidencia autorizada."
                        )
                    ],

                    "expected_result": (
                        "La máquina virtual queda "
                        "iniciada."
                    ),

                    "verification": (
                        "Comprobar posteriormente "
                        "el estado de la VM."
                    ),
                },

                "resolution_criteria": (
                    "La VM se encuentra en estado "
                    "operativo."
                ),

                "next_action": (
                    "execute_step"
                ),

                "escalation": {
                    "required": (
                        False
                    ),

                    "team": (
                        None
                    ),

                    "level": (
                        None
                    ),

                    "criteria": (
                        None
                    ),
                },

                "requires_clarification": (
                    False
                ),

                "missing_information": [],

                "source_documents": [
                    (
                        "TEST-PROC-VM-START "
                        "1.0"
                    )
                ],

                "confidence": (
                    0.99
                ),
            }
        )
    )


def create_execution_context(
) -> ProcedureExecutionContext:
    return ProcedureExecutionContext(
        request=(
            create_request()
        ),

        result=(
            create_procedure_result()
        ),

        execution_identity=(
            create_execution_identity()
        ),

        operational_context=(
            create_operational_context()
        ),
    )


def create_procedure_capability_registry(
) -> ProcedureCapabilityRegistry:
    """
    Binding gobernado por Python:

        procedure_id
        procedure_version
        step_id
                ↓
        azure.vm.start
    """

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
                    PROCEDURE_ID
                ),

                procedure_version=(
                    PROCEDURE_VERSION
                ),

                step_id=(
                    STEP_ID
                ),

                capability_id=(
                    "azure.vm.start"
                ),
            )
        ],
    )


def create_runtime(
) -> ProcedureRuntimeExecutor:
    """
    Runtime compuesto únicamente con registros
    gobernados por Python.
    """

    return ProcedureRuntimeExecutor(
        resource_identity_registry=(
            build_default_resource_identity_registry()
        ),

        procedure_capability_registry=(
            create_procedure_capability_registry()
        ),
    )


def test_bound_write_derives_operation_action_from_python_capability():
    """
    Garantía central de FASE 17.5.

    Procedure Agent interpreta:

        domain = azure
        kind = write
        target = VM_NAME

    pero NO decide VM_START.

    Python resuelve:

        procedure/version/step
                ↓
        azure.vm.start
                ↓
        OperationAction.VM_START
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    assert (
        context.result.step
        is not None
    )

    #
    # El contrato cognitivo NO dispone de
    # operation_action.
    #
    assert not hasattr(
        context.result.step,
        "operation_action",
    )

    state = (
        runtime
        ._build_runtime_state(
            context
        )
    )

    #
    # operation_action nace exclusivamente
    # de la capability gobernada por Python.
    #
    assert (
        state.step.operation_action
        == OperationAction.VM_START
    )

    assert (
        state.step.capability_id
        == "azure.vm.start"
    )

    assert (
        state.step.hitl_required
        is True
    )

    assert (
        state.step.operation_kind
        == OperationKind.WRITE
    )

    assert (
        state.step.operation_domain
        == "azure"
    )

    #
    # Los parámetros operacionales también
    # quedan fijados por la capability.
    #
    assert (
        state.step.required_parameters
        == [
            "subscription_id",
            "resource_group",
            "vm_name",
        ]
    )

    #
    # ResourceIdentityRegistry convierte el
    # target cognitivo en identidad ARM exacta.
    #
    assert (
        state.step.target_resource
        == CANONICAL_VM_RESOURCE_ID
    )

    #
    # Los valores concretos siguen procediendo
    # exclusivamente del OperationalContext.
    #
    resolved = {
        parameter.name:
            parameter.value

        for parameter
        in state.resolved_parameters
    }

    assert (
        resolved["subscription_id"]
        == SUBSCRIPTION_ID
    )

    assert (
        resolved["resource_group"]
        == RESOURCE_GROUP
    )

    assert (
        resolved["vm_name"]
        == VM_NAME
    )


def test_write_without_exact_capability_binding_is_blocked():
    """
    Un Procedure Agent no puede adquirir autoridad
    operacional simplemente declarando:

        operation_kind = write

    Sin binding exacto:

        procedure/version/step
                ↓
        capability

    el WRITE queda bloqueado antes del HITL.
    """

    capability_registry = (
        build_default_capability_registry()
    )

    empty_procedure_registry = (
        ProcedureCapabilityRegistry(
            capability_registry=(
                capability_registry
            ),

            bindings=[],
        )
    )

    runtime = (
        ProcedureRuntimeExecutor(
            resource_identity_registry=(
                build_default_resource_identity_registry()
            ),

            procedure_capability_registry=(
                empty_procedure_registry
            ),
        )
    )

    context = (
        create_execution_context()
    )

    with pytest.raises(
        ValueError,
        match="capability binding exacto",
    ):
        runtime._build_runtime_state(
            context
        )


def test_write_with_different_procedure_version_is_blocked():
    """
    Un binding para:

        procedure + 1.0 + step

    no autoriza automáticamente:

        procedure + 2.0 + step

    incluso aunque el resto de la operación parezca
    idéntico.
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    tampered_request = (
        context.request.model_copy(
            update={
                "procedure_version": (
                    "2.0"
                )
            }
        )
    )

    tampered_procedure = (
        context.result.procedure.model_copy(
            update={
                "version": (
                    "2.0"
                )
            }
        )
    )

    tampered_result = (
        context.result.model_copy(
            update={
                "procedure": (
                    tampered_procedure
                )
            }
        )
    )

    tampered_context = (
        context.model_copy(
            update={
                "request": (
                    tampered_request
                ),

                "result": (
                    tampered_result
                ),
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="capability binding exacto",
    ):
        runtime._build_runtime_state(
            tampered_context
        )


def test_bound_write_rejects_tampered_operation_domain():
    """
    El domain cognitivo debe coincidir exactamente
    con el domain de la capability gobernada.
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    assert (
        context.result.step
        is not None
    )

    tampered_step = (
        context.result.step.model_copy(
            update={
                "operation_domain": (
                    "database"
                )
            }
        )
    )

    tampered_result = (
        context.result.model_copy(
            update={
                "step": (
                    tampered_step
                )
            }
        )
    )

    tampered_context = (
        context.model_copy(
            update={
                "result": (
                    tampered_result
                )
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="operation_domain",
    ):
        runtime._build_runtime_state(
            tampered_context
        )


def test_bound_write_rejects_tampered_operation_kind():
    """
    Un binding WRITE no puede convertirse en READ
    ni viceversa mediante una salida cognitiva
    manipulada.
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    assert (
        context.result.step
        is not None
    )

    tampered_step = (
        context.result.step.model_copy(
            update={
                "operation_kind": (
                    "read"
                )
            }
        )
    )

    tampered_result = (
        context.result.model_copy(
            update={
                "step": (
                    tampered_step
                )
            }
        )
    )

    tampered_context = (
        context.model_copy(
            update={
                "result": (
                    tampered_result
                )
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="operation_kind",
    ):
        runtime._build_runtime_state(
            tampered_context
        )


def test_bound_write_rejects_tampered_required_parameters():
    """
    La lista de parámetros operacionales debe
    coincidir exactamente con la capability.

    No aceptamos:

    - parámetros faltantes;
    - parámetros añadidos;
    - parámetros reordenados.
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    assert (
        context.result.step
        is not None
    )

    tampered_step = (
        context.result.step.model_copy(
            update={
                "required_parameters": [
                    "vm_name",
                    "resource_group",
                    "subscription_id",
                ]
            }
        )
    )

    tampered_result = (
        context.result.model_copy(
            update={
                "step": (
                    tampered_step
                )
            }
        )
    )

    tampered_context = (
        context.model_copy(
            update={
                "result": (
                    tampered_result
                )
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="required_parameters",
    ):
        runtime._build_runtime_state(
            tampered_context
        )


def test_bound_write_rejects_tampered_authoritative_resource_type():
    """
    Una capability registrada para:

        Microsoft.Compute/virtualMachines

    no puede utilizarse contra otro resource_type,
    aunque procedure/version/step sigan siendo
    correctos.
    """

    runtime = (
        create_runtime()
    )

    context = (
        create_execution_context()
    )

    tampered_operational_context = (
        context.operational_context.model_copy(
            update={
                "resource_type": (
                    "Microsoft.Compute/"
                    "virtualMachineScaleSets"
                )
            }
        )
    )

    tampered_context = (
        context.model_copy(
            update={
                "operational_context": (
                    tampered_operational_context
                )
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="resource_type",
    ):
        runtime._build_runtime_state(
            tampered_context
        )
REAL_VM_PROCEDURES = [
    (
        "NTTSY-SBX-AZ-VM-001",
        (
            "Arranque de máquina virtual Azure "
            "en estado Stopped (Allocated)"
        ),
    ),
    (
        "NTTSY-SBX-AZ-VM-002",
        (
            "Arranque de máquina virtual Azure "
            "en estado Deallocated"
        ),
    ),
]


def create_real_vm_execution_context(
    *,
    procedure_id: str,
    procedure_name: str,
) -> ProcedureExecutionContext:
    """
    Convierte el contexto sintético existente en un
    contexto cognitivo equivalente al que producirían
    los procedimientos VM reales.

    No introduce authority operacional.

    Sólo sustituye:

        procedure_id
        procedure_name
        procedure_version
        step_id

    La capability seguirá naciendo exclusivamente del
    registry default gobernado por Python.
    """

    context = (
        create_execution_context()
    )

    request = (
        context.request.model_copy(
            update={
                "procedure_id": (
                    procedure_id
                ),

                "procedure_name": (
                    procedure_name
                ),

                "procedure_version": (
                    "1.0"
                ),
            }
        )
    )

    procedure = (
        context.result.procedure.model_copy(
            update={
                "id": (
                    procedure_id
                ),

                "name": (
                    procedure_name
                ),

                "version": (
                    "1.0"
                ),
            }
        )
    )

    assert (
        context.result.step
        is not None
    )

    step = (
        context.result.step.model_copy(
            update={
                "id": (
                    "1"
                )
            }
        )
    )

    result = (
        context.result.model_copy(
            update={
                "procedure": (
                    procedure
                ),

                "total_steps": (
                    1
                ),

                "current_step": (
                    1
                ),

                "step": (
                    step
                ),
            }
        )
    )

    return (
        context.model_copy(
            update={
                "request": (
                    request
                ),

                "result": (
                    result
                ),
            }
        )
    )


@pytest.mark.parametrize(
    (
        "procedure_id",
        "procedure_name",
    ),
    REAL_VM_PROCEDURES,
    ids=[
        "vm-stopped-allocated",
        "vm-deallocated",
    ],
)
def test_default_runtime_resolves_real_vm_start_procedures(
    procedure_id,
    procedure_name,
):
    """
    Garantía productiva de FASE 18.0.

    Procedure Agent sólo proporciona:

        procedure/version/step
        operation_domain
        operation_kind
        required_parameters

    El Runtime DEFAULT debe resolver:

        procedure/version/step
                ↓
        azure.vm.start
                ↓
        OperationAction.VM_START

    sin inyección de registry de test.
    """

    runtime = (
        ProcedureRuntimeExecutor()
    )

    context = (
        create_real_vm_execution_context(
            procedure_id=(
                procedure_id
            ),

            procedure_name=(
                procedure_name
            ),
        )
    )

    state = (
        runtime._build_runtime_state(
            context
        )
    )

    assert (
        state.procedure.id
        == procedure_id
    )

    assert (
        state.procedure.version
        == "1.0"
    )

    assert (
        state.step.id
        == "1"
    )

    assert (
        state.step.capability_id
        == "azure.vm.start"
    )

    assert (
        state.step.operation_action
        == OperationAction.VM_START
    )

    assert (
        state.step.operation_domain
        == "azure"
    )

    assert (
        state.step.operation_kind
        == OperationKind.WRITE
    )

    assert (
        state.step.hitl_required
        is True
    )

    assert (
        state.step.required_parameters
        == [
            "subscription_id",
            "resource_group",
            "vm_name",
        ]
    )

    assert (
        state.step.target_resource
        == CANONICAL_VM_RESOURCE_ID
    )

    resolved = {
        parameter.name:
            parameter.value

        for parameter
        in state.resolved_parameters
    }

    assert (
        resolved["subscription_id"]
        == SUBSCRIPTION_ID
    )

    assert (
        resolved["resource_group"]
        == RESOURCE_GROUP
    )

    assert (
        resolved["vm_name"]
        == VM_NAME
    )