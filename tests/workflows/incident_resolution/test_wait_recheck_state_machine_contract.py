import ast
import importlib
import inspect

import pytest

from pathlib import Path


CORE_LEDGER_MODULE = (
    "src.workflows.incident_resolution."
    "wait_recheck_consumption_ledger"
)

AZURE_SQL_LEDGER_MODULE = (
    "src.persistence.azure_sql."
    "wait_recheck_consumption_ledger"
)


def _core_module():
    return importlib.import_module(
        CORE_LEDGER_MODULE
    )


def _azure_sql_module():
    return importlib.import_module(
        AZURE_SQL_LEDGER_MODULE
    )


def test_core_ledger_exposes_explicit_crash_safe_state_machine_contract():
    module = _core_module()

    assert hasattr(
        module,
        "WaitRecheckStatus",
    )

    assert hasattr(
        module,
        "WaitRecheckBeginResult",
    )

    protocol = getattr(
        module,
        "WaitRecheckConsumptionLedger",
    )

    source = inspect.getsource(
        protocol
    )

    assert "def begin(" in source
    assert "def complete(" in source
    assert "def status(" in source


def test_in_memory_begin_can_resume_until_completion_then_blocks():
    module = _core_module()

    ledger = (
        module
        .InMemoryWaitRecheckConsumptionLedger()
    )

    begin = getattr(
        ledger,
        "begin",
        None,
    )

    complete = getattr(
        ledger,
        "complete",
        None,
    )

    status = getattr(
        ledger,
        "status",
        None,
    )

    assert callable(begin)
    assert callable(complete)
    assert callable(status)

    recheck_id = (
        "rchk-state-machine-memory"
    )

    first = begin(
        recheck_id
    )

    assert (
        first.value
        == "claimed"
    )

    assert (
        status(
            recheck_id
        ).value
        == "in_progress"
    )

    second = begin(
        recheck_id
    )

    assert (
        second.value
        == "resumed"
    )

    complete(
        recheck_id
    )

    assert (
        status(
            recheck_id
        ).value
        == "completed"
    )

    complete(
        recheck_id
    )

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    try:
        begin(
            recheck_id
        )
    except error_type:
        pass
    else:
        raise AssertionError(
            "COMPLETED recheck debe bloquear begin()."
        )


def test_sqlite_state_machine_is_durable_across_process_instances(
    tmp_path,
):
    module = _core_module()

    ledger_type = (
        module
        .SqliteWaitRecheckConsumptionLedger
    )

    path = (
        tmp_path
        / "wait-state-machine.db"
    )

    recheck_id = (
        "rchk-state-machine-sqlite"
    )

    ledger_a = ledger_type(
        path
    )

    assert callable(
        getattr(
            ledger_a,
            "begin",
            None,
        )
    )

    first = ledger_a.begin(
        recheck_id
    )

    assert first.value == "claimed"

    ledger_b = ledger_type(
        path
    )

    assert (
        ledger_b.status(
            recheck_id
        ).value
        == "in_progress"
    )

    resumed = ledger_b.begin(
        recheck_id
    )

    assert resumed.value == "resumed"

    ledger_b.complete(
        recheck_id
    )

    ledger_c = ledger_type(
        path
    )

    assert (
        ledger_c.status(
            recheck_id
        ).value
        == "completed"
    )

    ledger_c.complete(
        recheck_id
    )

    error_type = (
        module
        .WaitRecheckAlreadyConsumedError
    )

    try:
        ledger_c.begin(
            recheck_id
        )
    except error_type:
        pass
    else:
        raise AssertionError(
            "COMPLETED SQLite recheck "
            "debe bloquear begin()."
        )


def test_azure_sql_adapter_exposes_same_state_machine_surface():
    module = _azure_sql_module()

    adapter = getattr(
        module,
        "AzureSqlWaitRecheckConsumptionLedger",
    )

    for method_name in (
        "begin",
        "complete",
        "status",
    ):
        assert callable(
            getattr(
                adapter,
                method_name,
                None,
            )
        )

    source = inspect.getsource(
        module
    ).lower()

    assert "create table" not in source
    assert "alter table" not in source

    assert "in_progress" in source
    assert "completed" in source


def test_migration_005_upgrades_existing_rows_to_completed_fail_closed():
    path = Path(
        "platform/azure-sql/migrations/"
        "005_wait_recheck_state.sql"
    )

    assert path.is_file()

    source = path.read_text(
        encoding="utf-8"
    )

    lowered = source.lower()

    assert (
        "alter table "
        "dbo.wait_recheck_consumption_claims"
        in lowered
    )

    assert "status" in lowered
    assert "nvarchar" in lowered

    assert "in_progress" in lowered
    assert "completed" in lowered

    assert "default" in lowered
    assert "check" in lowered

    assert "create table" not in lowered
    assert "drop table" not in lowered
    assert "truncate table" not in lowered


def test_procedure_validation_request_can_carry_python_owned_wait_recheck_id():
    module = importlib.import_module(
        "src.workflows.incident_resolution."
        "procedure_validation_models"
    )

    request_type = getattr(
        module,
        "ProcedureValidationRequest",
    )

    assert (
        "wait_recheck_id"
        in request_type.model_fields
    )

    field = (
        request_type
        .model_fields[
            "wait_recheck_id"
        ]
    )

    assert field.default is None


def test_wait_response_uses_begin_and_tags_fresh_validation_request():
    transition_path = Path(
        "src/workflows/incident_resolution/"
        "executors/procedure_transition.py"
    )

    wait_path = Path(
        "src/workflows/incident_resolution/"
        "wait_recheck.py"
    )

    transition_source = (
        transition_path
        .read_text(
            encoding="utf-8"
        )
    )

    wait_source = (
        wait_path
        .read_text(
            encoding="utf-8"
        )
    )

    assert (
        "_wait_recheck_consumption_ledger.begin"
        in transition_source
    )

    assert (
        "_wait_recheck_consumption_ledger.claim("
        not in transition_source
    )

    assert (
        "wait_recheck_id="
        in wait_source
    )


def test_vm_observation_completes_wait_recheck_before_any_azure_read():
    path = Path(
        "src/workflows/incident_resolution/"
        "executors/"
        "azure_vm_post_operation_observation.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    handle = None

    for node in ast.walk(
        tree
    ):
        if (
            isinstance(
                node,
                ast.AsyncFunctionDef,
            )
            and node.name == "handle"
        ):
            handle = node
            break

    assert handle is not None

    complete_lines = []
    read_reference_lines = []

    for node in ast.walk(
        handle
    ):
        if (
            isinstance(
                node,
                ast.Call,
            )
            and isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "complete"
        ):
            complete_lines.append(
                node.lineno
            )

        if (
            isinstance(
                node,
                ast.Attribute,
            )
            and node.attr
            == "read_power_state"
        ):
            read_reference_lines.append(
                node.lineno
            )

    assert len(
        complete_lines
    ) >= 1

    assert len(
        read_reference_lines
    ) == 1

    assert min(
        complete_lines
    ) < min(
        read_reference_lines
    )

    assert (
        "wait_recheck_id"
        in source
    )


def test_workflow_injects_same_wait_ledger_into_transition_and_observation():

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

    transition = one_call(wf, "ProcedureTransitionExecutor")
    name_argument(forwarded, "wait_recheck_consumption_ledger", "wait_recheck_ledger")
    name_argument(transition, "wait_recheck_consumption_ledger", "wait_recheck_ledger")
    name_argument(observed, "wait_recheck_consumption_ledger", "wait_recheck_consumption_ledger")
    parameters = factory.args.posonlyargs + factory.args.args + factory.args.kwonlyargs
    assert sum(a.arg == "wait_recheck_consumption_ledger" for a in parameters) == 1
    assert not any(isinstance(n, ast.Name) and n.id == "wait_recheck_consumption_ledger"
                   and isinstance(n.ctx, (ast.Store, ast.Del)) for n in ast.walk(factory))
    # The shared reference must not be rebound between its two consumers.
    writes = [n for n in ast.walk(wf) if isinstance(n, ast.Name)
              and n.id == "wait_recheck_ledger" and isinstance(n.ctx, (ast.Store, ast.Del))]
    assert writes and all(n.lineno < min(forwarded.lineno, transition.lineno) for n in writes)

@pytest.mark.asyncio
async def test_real_vm_observation_completes_before_reader_and_preserves_wait_identity():
    from src.workflows.incident_resolution.executors.azure_vm_post_operation_observation import (
        AzureVmPostOperationObservationExecutor,
    )

    from src.workflows.incident_resolution.wait_recheck import (
        WaitRecheckSignal,
        consume_wait_recheck_signal,
    )

    from src.workflows.incident_resolution.wait_recheck_consumption_ledger import (
        InMemoryWaitRecheckConsumptionLedger,
        WaitRecheckStatus,
    )

    from tests.workflows.incident_resolution.test_wait_recheck_consumption_ledger_contract import (
        _wait_state_and_request,
    )

    (
        waiting_state,
        request,
    ) = _wait_state_and_request()

    signal = WaitRecheckSignal(
        recheck_id=request.recheck_id
    )

    (
        _,
        validation_request,
    ) = consume_wait_recheck_signal(
        state=waiting_state,
        original_request=request,
        signal=signal,
    )

    assert (
        validation_request.wait_recheck_id
        == request.recheck_id
    )

    ledger = (
        InMemoryWaitRecheckConsumptionLedger()
    )

    begin_result = ledger.begin(
        request.recheck_id
    )

    assert begin_result.value == "claimed"

    observed_statuses = []

    class Reader:
        def read_power_state(
            self,
            *,
            subscription_id,
            resource_group,
            vm_name,
        ):
            observed_statuses.append(
                ledger.status(
                    request.recheck_id
                )
            )

            return "PowerState/running"

    class Context:
        def __init__(
            self,
        ):
            self.messages = []

        async def send_message(
            self,
            value,
        ):
            self.messages.append(
                value
            )

    ctx = Context()

    executor = (
        AzureVmPostOperationObservationExecutor(
            reader=Reader(),
            wait_recheck_consumption_ledger=ledger,
        )
    )

    await executor.handle(
        validation_request,
        ctx,
    )

    assert observed_statuses == [
        WaitRecheckStatus.COMPLETED
    ]

    assert (
        ledger.status(
            request.recheck_id
        )
        == WaitRecheckStatus.COMPLETED
    )

    assert len(ctx.messages) == 1

    enriched = ctx.messages[0]

    assert (
        enriched.wait_recheck_id
        == request.recheck_id
    )

    assert (
        enriched.post_operation_observation
        is not None
    )

    assert (
        enriched.post_operation_observation
        .success
        is True
    )