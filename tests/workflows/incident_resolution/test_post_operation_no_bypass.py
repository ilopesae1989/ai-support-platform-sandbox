import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

WORKFLOW_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "workflow.py"
)

AZURE_OPERATIONS_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "executors"
    / "azure_operations.py"
)

REGISTRATION_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "executors"
    / "operation_result_registration.py"
)

OBSERVATION_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "executors"
    / "azure_vm_post_operation_observation.py"
)

VALIDATION_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "executors"
    / "procedure_validation.py"
)

TRANSITION_PATH = (
    ROOT
    / "src"
    / "workflows"
    / "incident_resolution"
    / "executors"
    / "procedure_transition.py"
)


def parse_file(
    path: Path,
) -> ast.Module:
    return ast.parse(
        path.read_text(
            encoding="utf-8"
        )
    )


def find_class(
    tree: ast.Module,
    name: str,
) -> ast.ClassDef:
    matches = [
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name == name
        )
    ]

    assert len(matches) == 1, (
        f"{name}: expected exactly one class, "
        f"found={len(matches)}"
    )

    return matches[0]


def find_function(
    tree: ast.AST,
    name: str,
):
    matches = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == name
        )
    ]

    assert len(matches) == 1, (
        f"{name}: expected exactly one function, "
        f"found={len(matches)}"
    )

    return matches[0]


def find_class_method(
    tree: ast.Module,
    class_name: str,
    method_name: str,
):
    cls = find_class(
        tree,
        class_name,
    )

    matches = [
        node
        for node in cls.body
        if (
            isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == method_name
        )
    ]

    assert len(matches) == 1, (
        f"{class_name}.{method_name}: "
        f"expected exactly one method, "
        f"found={len(matches)}"
    )

    return matches[0]


def workflow_edges():
    tree = parse_file(
        WORKFLOW_PATH
    )

    function = find_function(
        tree,
        "build_incident_resolution_workflow",
    )

    edges = []

    for node in ast.walk(
        function
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if node.func.attr != "add_edge":
            continue

        assert len(node.args) >= 2

        source = node.args[0]
        target = node.args[1]

        assert isinstance(
            source,
            ast.Name,
        )

        assert isinstance(
            target,
            ast.Name,
        )

        edges.append(
            (
                source.id,
                target.id,
            )
        )

    return edges


def workflow_output_from():
    tree = parse_file(
        WORKFLOW_PATH
    )

    function = find_function(
        tree,
        "build_incident_resolution_workflow",
    )

    builders = []

    for node in ast.walk(
        function
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if node.func.id == "WorkflowBuilder":
            builders.append(
                node
            )

    assert len(builders) == 1

    builder = builders[0]

    output_keywords = [
        keyword
        for keyword in builder.keywords
        if keyword.arg == "output_from"
    ]

    assert len(output_keywords) == 1

    output_value = (
        output_keywords[0].value
    )

    assert isinstance(
        output_value,
        ast.List,
    )

    outputs = []

    for element in output_value.elts:
        assert isinstance(
            element,
            ast.Name,
        )

        outputs.append(
            element.id
        )

    return outputs


def context_calls(
    method,
):
    calls = []

    for node in ast.walk(
        method
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Attribute,
        ):
            continue

        if not isinstance(
            node.func.value,
            ast.Name,
        ):
            continue

        if node.func.value.id != "ctx":
            continue

        if node.func.attr not in {
            "send_message",
            "yield_output",
        }:
            continue

        calls.append(
            node
        )

    return calls


def outgoing(
    edges,
    executor_id,
):
    return [
        target
        for source, target in edges
        if source == executor_id
    ]


def incoming(
    edges,
    executor_id,
):
    return [
        source
        for source, target in edges
        if target == executor_id
    ]


def test_post_operation_graph_is_single_linear_chain():
    """
    Azure Operations no puede saltarse
    Registration, Observation, Validation ni
    Transition.

    En FASE 22.6, CONTINUE puede salir únicamente
    de ProcedureTransition hacia Procedure.
    """

    edges = workflow_edges()

    assert outgoing(
        edges,
        "azure_route",
    ) == [
        "operation_result_registration",
    ]

    assert incoming(
        edges,
        "operation_result_registration",
    ) == [
        "azure_route",
    ]

    assert outgoing(
        edges,
        "operation_result_registration",
    ) == [
        "azure_vm_post_operation_observation",
    ]

    assert incoming(
        edges,
        "azure_vm_post_operation_observation",
    ) == [
        "operation_result_registration",
    ]

    assert outgoing(
        edges,
        "azure_vm_post_operation_observation",
    ) == [
        "procedure_validation",
    ]

    assert incoming(
        edges,
        "procedure_validation",
    ) == [
        "azure_vm_post_operation_observation",
    ]

    assert outgoing(
        edges,
        "procedure_validation",
    ) == [
        "procedure_transition",
    ]

    assert incoming(
        edges,
        "procedure_transition",
    ) == [
        "procedure_validation",
    ]

    assert outgoing(
        edges,
        "procedure_transition",
    ) == [
        "procedure",
    ]



def test_only_transition_is_terminal_output_of_post_operation_chain():
    """
    Ningún executor anterior al Transition Gate
    puede ser output terminal del workflow.
    """

    outputs = workflow_output_from()

    assert (
        "procedure_transition"
        in outputs
    )

    forbidden = {
        "azure_pre_call",
        "operation_start",
        "azure_route",
        "operation_result_registration",
        "azure_vm_post_operation_observation",
        "procedure_validation",
    }

    assert forbidden.isdisjoint(
        outputs
    )


def test_registration_and_validation_only_send_downstream():
    """
    Registration y Procedure Validation son
    obligatoriamente intermedios.
    """

    registration_tree = parse_file(
        REGISTRATION_PATH
    )

    registration_handle = (
        find_class_method(
            registration_tree,
            "OperationResultRegistrationExecutor",
            "handle",
        )
    )

    registration_calls = context_calls(
        registration_handle
    )

    assert len(
        registration_calls
    ) == 1

    assert (
        registration_calls[0]
        .func
        .attr
        == "send_message"
    )

    observation_tree = parse_file(
        OBSERVATION_PATH
    )

    observation_handle = (
        find_class_method(
            observation_tree,
            "AzureVmPostOperationObservationExecutor",
            "handle",
        )
    )

    observation_calls = context_calls(
        observation_handle
    )

    assert len(
        observation_calls
    ) >= 1

    assert all(
        (
            call.func.attr
            == "send_message"
        )
        for call in observation_calls
    )

    validation_tree = parse_file(
        VALIDATION_PATH
    )

    validation_handle = (
        find_class_method(
            validation_tree,
            "ProcedureValidationExecutor",
            "handle",
        )
    )

    validation_calls = context_calls(
        validation_handle
    )

    assert len(
        validation_calls
    ) == 1

    assert (
        validation_calls[0]
        .func
        .attr
        == "send_message"
    )


def test_transition_has_governed_continue_and_terminal_output_surfaces():
    """
    ProcedureTransitionExecutor tiene exactamente
    dos superficies de salida gobernadas:

    - send_message exclusivamente para CONTINUE;
    - yield_output para decisiones terminales.

    El mensaje CONTINUE se dirige al ID canónico
    procedure_execution.
    """

    tree = parse_file(
        TRANSITION_PATH
    )

    handle = find_class_method(
        tree,
        "ProcedureTransitionExecutor",
        "handle",
    )

    calls = context_calls(
        handle
    )

    attributes = [
        call.func.attr
        for call in calls
    ]

    assert (
        attributes.count(
            "send_message"
        )
        == 1
    )

    assert (
        attributes.count(
            "yield_output"
        )
        == 1
    )

    assert len(calls) == 2

    send_calls = [
        call
        for call in calls
        if (
            call.func.attr
            == "send_message"
        )
    ]

    assert len(
        send_calls
    ) == 1

    send_call = (
        send_calls[0]
    )

    target_keywords = [
        keyword
        for keyword in send_call.keywords
        if keyword.arg == "target_id"
    ]

    assert len(
        target_keywords
    ) == 1

    target = (
        target_keywords[0]
        .value
    )

    assert isinstance(
        target,
        ast.Constant,
    )

    assert (
        target.value
        == "procedure_execution"
    )



def test_azure_operations_emits_same_result_to_both_surfaces():
    """
    Azure Operations envía la misma variable
    result tanto downstream como a yield_output.

    No se permite reconstruir un segundo
    AzureOperationResult entre ambas superficies.
    """

    tree = parse_file(
        AZURE_OPERATIONS_PATH
    )

    emit_result = find_class_method(
        tree,
        "AzureOperationsExecutor",
        "_emit_result",
    )

    calls = context_calls(
        emit_result
    )

    attributes = [
        call.func.attr
        for call in calls
    ]

    assert (
        attributes.count(
            "send_message"
        )
        == 1
    )

    assert (
        attributes.count(
            "yield_output"
        )
        == 1
    )

    assert len(calls) == 2

    for call in calls:
        assert len(
            call.args
        ) == 1

        argument = call.args[0]

        assert isinstance(
            argument,
            ast.Name,
        )

        assert (
            argument.id
            == "result"
        )


def test_workflow_injects_reader_only_into_observation_executor():
    tree = parse_file(
        WORKFLOW_PATH
    )

    function = find_function(
        tree,
        "build_incident_resolution_workflow",
    )

    calls = [
        node
        for node in ast.walk(
            function
        )
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "AzureVmPostOperationObservationExecutor"
        )
    ]

    assert len(calls) == 1

    call = calls[0]

    reader_keywords = [
        keyword
        for keyword in call.keywords
        if keyword.arg == "reader"
    ]

    assert len(
        reader_keywords
    ) == 1

    value = (
        reader_keywords[0]
        .value
    )

    # reader=(azure_vm_power_state_reader)
    assert isinstance(
        value,
        ast.Name,
    )

    assert (
        value.id
        == "azure_vm_power_state_reader"
    )
