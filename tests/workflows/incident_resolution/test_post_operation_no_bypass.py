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

    def single_assignment(
        name: str,
    ) -> ast.AST:
        matches = [
            node.value
            for node in function.body
            if (
                isinstance(
                    node,
                    ast.Assign,
                )
                and len(
                    node.targets
                ) == 1
                and isinstance(
                    node.targets[0],
                    ast.Name,
                )
                and node.targets[0].id
                == name
            )
        ]

        assert len(
            matches
        ) == 1

        return matches[0]

    legacy_outputs_value = (
        single_assignment(
            "legacy_outputs"
        )
    )

    assert isinstance(
        legacy_outputs_value,
        ast.ListComp,
    )

    assert isinstance(
        legacy_outputs_value.elt,
        ast.Name,
    )

    assert (
        legacy_outputs_value.elt.id
        == "target"
    )

    assert len(
        legacy_outputs_value.generators
    ) == 1

    legacy_outputs_generator = (
        legacy_outputs_value.generators[0]
    )

    assert isinstance(
        legacy_outputs_generator.iter,
        ast.Name,
    )

    assert (
        legacy_outputs_generator.iter.id
        == "active_legacy_routes"
    )

    active_legacy_value = (
        single_assignment(
            "active_legacy_routes"
        )
    )

    assert isinstance(
        active_legacy_value,
        ast.Call,
    )

    assert isinstance(
        active_legacy_value.func,
        ast.Name,
    )

    assert (
        active_legacy_value.func.id
        == "tuple"
    )

    assert len(
        active_legacy_value.args
    ) == 1

    active_generator = (
        active_legacy_value.args[0]
    )

    assert isinstance(
        active_generator,
        ast.GeneratorExp,
    )

    assert len(
        active_generator.generators
    ) == 1

    active_source = (
        active_generator.generators[0]
        .iter
    )

    assert isinstance(
        active_source,
        ast.Name,
    )

    assert (
        active_source.id
        == "legacy_routes"
    )

    legacy_routes_value = (
        single_assignment(
            "legacy_routes"
        )
    )

    assert isinstance(
        legacy_routes_value,
        ast.Tuple,
    )

    legacy_targets = []

    for route in (
        legacy_routes_value.elts
    ):
        assert isinstance(
            route,
            ast.Tuple,
        )

        assert len(
            route.elts
        ) == 3

        target = (
            route.elts[2]
        )

        assert isinstance(
            target,
            ast.Name,
        )

        legacy_targets.append(
            target.id
        )

    outputs = []

    spread_count = 0

    for element in output_value.elts:
        if isinstance(
            element,
            ast.Name,
        ):
            outputs.append(
                element.id
            )
            continue

        assert isinstance(
            element,
            ast.Starred,
        )

        assert isinstance(
            element.value,
            ast.Name,
        )

        assert (
            element.value.id
            == "legacy_outputs"
        )

        spread_count += 1

        outputs.extend(
            legacy_targets
        )

    assert spread_count == 1

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


def test_post_operation_graph_preserves_linear_chain_with_governed_wait_recheck():
    """
    Azure Operations no puede saltarse
    Registration, Observation, Validation ni
    Transition.

    FASE 22.8 añade una única vuelta gobernada:

        ProcedureTransition
            -> fresh Observation

    exclusivamente después de una señal WAIT
    correlacionada.

    La cadena operacional inicial sigue siendo
    obligatoriamente lineal.
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

    assert set(
        incoming(
            edges,
            "azure_vm_post_operation_observation",
        )
    ) == {
        "operation_result_registration",
        "procedure_transition",
    }

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

    assert set(
        outgoing(
            edges,
            "procedure_transition",
        )
    ) == {
        "procedure",
        "azure_vm_post_operation_observation",
    }



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


def test_transition_has_governed_continue_repeat_and_terminal_output_surfaces():
    """
    ProcedureTransitionExecutor tiene exactamente
    tres superficies explícitas:

    - CONTINUE -> send_message;
    - REPEAT   -> send_message;
    - WAIT / RESOLVED / ESCALATE / BLOCKED
      -> yield_output.

    Ambos mensajes activos se dirigen al executor
    canónico procedure_execution.
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
        == 2
    )

    assert (
        attributes.count(
            "yield_output"
        )
        == 1
    )

    assert len(calls) == 3

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
    ) == 2

    message_names = set()

    for send_call in send_calls:
        assert len(
            send_call.args
        ) == 1

        argument = (
            send_call.args[0]
        )

        assert isinstance(
            argument,
            ast.Name,
        )

        message_names.add(
            argument.id
        )

        target_keywords = [
            keyword
            for keyword
            in send_call.keywords
            if keyword.arg
            == "target_id"
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

    assert message_names == {
        "next_input",
        "repeat_input",
    }



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

    # F26.3: follow the composition boundary; keep the security invariant.
    base = Path(__file__).resolve().parents[3] / "src/workflows/incident_resolution"

    def read_function(path, name):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        assert len(matches) == 1, name
        return matches[0]

    def assert_exact_selector_spread(fn, call, expanded):
        # F27.3-R14F: permit only the typed single-key opt-in registry.
        # The pre-existing reader and WAIT checks below remain unchanged.
        registry = "capability_foundry_agent_binding_registry"
        assert isinstance(expanded.value, ast.Name)
        assert isinstance(expanded.value.ctx, ast.Load)
        assert expanded.value.id == "selector_options"

        initializers = [s for s in fn.body if isinstance(s, ast.Assign)
                        and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name)
                        and s.targets[0].id == "selector_options"]
        assert len(initializers) == 1
        initializer = initializers[0]
        assert isinstance(initializer.value, ast.Dict)
        assert initializer.value.keys == initializer.value.values == []
        assert initializer.lineno < call.lineno

        def enabled(node):
            return (isinstance(node, ast.Compare)
                    and isinstance(node.left, ast.Name)
                    and node.left.id == registry
                    and len(node.ops) == len(node.comparators) == 1
                    and isinstance(node.ops[0], ast.IsNot)
                    and isinstance(node.comparators[0], ast.Constant)
                    and node.comparators[0].value is None)

        def bad_type(node):
            if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, ast.Not):
                return False
            c = node.operand
            return (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == "isinstance" and not c.keywords
                    and len(c.args) == 2
                    and isinstance(c.args[0], ast.Name) and c.args[0].id == registry
                    and isinstance(c.args[1], ast.Name)
                    and c.args[1].id == "CapabilityFoundryAgentBindingRegistry")

        def type_error(stmt):
            return (isinstance(stmt, ast.Raise)
                    and isinstance(stmt.exc, ast.Call)
                    and isinstance(stmt.exc.func, ast.Name)
                    and stmt.exc.func.id == "TypeError")

        gates = [s for s in fn.body if isinstance(s, ast.If) and enabled(s.test)]
        assert len(gates) == 1
        gate = gates[0]
        assert not gate.orelse
        assert initializer.lineno < gate.lineno < call.lineno
        assert len(gate.body) in (1, 2)

        mutation = gate.body[-1]
        assert isinstance(mutation, ast.Assign) and len(mutation.targets) == 1
        key = mutation.targets[0]
        assert isinstance(key, ast.Subscript) and isinstance(key.ctx, ast.Store)
        assert isinstance(key.value, ast.Name) and key.value.id == "selector_options"
        assert isinstance(key.slice, ast.Constant) and key.slice.value == registry
        assert isinstance(mutation.value, ast.Name) and mutation.value.id == registry
        assert mutation.lineno < call.lineno

        if len(gate.body) == 2:
            check = gate.body[0]
            assert isinstance(check, ast.If) and bad_type(check.test)
            assert not check.orelse and len(check.body) == 1
            assert type_error(check.body[0])
            assert check.lineno < mutation.lineno
        else:
            checks = [s for s in fn.body if isinstance(s, ast.If)
                      and isinstance(s.test, ast.BoolOp)
                      and isinstance(s.test.op, ast.And)
                      and len(s.test.values) == 2
                      and enabled(s.test.values[0])
                      and bad_type(s.test.values[1])]
            assert len(checks) == 1
            check = checks[0]
            assert not check.orelse and len(check.body) == 1
            assert type_error(check.body[0])
            assert check.lineno < initializer.lineno

        # No alias, reassignment, update(), extra consumer or silent fallback.
        references = [n for n in ast.walk(fn)
                      if isinstance(n, ast.Name) and n.id == "selector_options"]
        assert len(references) == 3
        assert {id(n) for n in references} == {
            id(initializer.targets[0]), id(key.value), id(expanded.value)
        }

    def one_call(fn, name):
        matches = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Name) and n.func.id == name]
        assert len(matches) == 1, name
        call = matches[0]
        assert not call.args
        named = [k.arg for k in call.keywords if k.arg is not None]
        assert len(named) == len(set(named))
        expansions = [k for k in call.keywords if k.arg is None]
        if name == "build_azure_domain_composition":
            assert named == ["agents", "operation_dispatch_ledger",
                             "wait_recheck_consumption_ledger",
                             "azure_vm_power_state_reader"]
            assert len(expansions) == 1 and call.keywords[-1] is expansions[0]
            assert "capability_foundry_agent_binding_registry" not in named
            assert_exact_selector_spread(fn, call, expansions[0])
        elif name == "AzureOperationsExecutor":
            assert named == ["agents", "operation_dispatch_ledger"]
            assert len(expansions) == 1 and call.keywords[-1] is expansions[0]
            assert "capability_foundry_agent_binding_registry" not in named
            assert_exact_selector_spread(fn, call, expansions[0])
        else:
            assert not expansions
        return call

    def name_argument(call, keyword, name):
        matches = [k.value for k in call.keywords if k.arg == keyword]
        assert len(matches) == 1, keyword
        value = matches[0]
        assert isinstance(value, ast.Name) and isinstance(value.ctx, ast.Load)
        assert value.id == name, keyword
        return value

    def assigned(fn, name):
        matches = [n.value for n in fn.body if isinstance(n, ast.Assign)
                   and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                   and n.targets[0].id == name]
        writes = [n for n in ast.walk(fn) if isinstance(n, ast.Name)
                  and n.id == name and isinstance(n.ctx, (ast.Store, ast.Del))]
        assert len(matches) == len(writes) == 1, name
        return matches[0]

    wf = read_function(base / "workflow.py", "build_incident_resolution_workflow")
    factory = read_function(base / "azure_domain_composition.py", "build_azure_domain_composition")
    forwarded = one_call(wf, "build_azure_domain_composition")
    governed_executor = one_call(factory, "AzureOperationsExecutor")
    name_argument(governed_executor, "agents", "agents")
    observed = one_call(factory, "AzureVmPostOperationObservationExecutor")
    assert assigned(wf, "azure_composition") is forwarded
    assert assigned(factory, "observation") is observed
    assert ast.unparse(assigned(wf, "azure_vm_post_operation_observation")) == (
        "azure_composition.post_operation_observation"
    )
    returned = one_call(factory, "AzureDomainComposition")
    exits = [n for n in factory.body if isinstance(n, ast.Return)]
    assert len(exits) == 1 and exits[0].value is returned
    name_argument(returned, "post_operation_observation", "observation")

    for fn, call, keyword in (
        (wf, forwarded, "azure_vm_power_state_reader"),
        (factory, observed, "reader"),
    ):
        value = name_argument(call, keyword, "azure_vm_power_state_reader")
        parameters = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
        assert sum(a.arg == "azure_vm_power_state_reader" for a in parameters) == 1
        uses = [n for n in ast.walk(fn) if isinstance(n, ast.Name)
                and n.id == "azure_vm_power_state_reader"]
        # No substitution, reassignment, extra recipient or unused forwarding.
        assert len(uses) == 1 and uses[0] is value
