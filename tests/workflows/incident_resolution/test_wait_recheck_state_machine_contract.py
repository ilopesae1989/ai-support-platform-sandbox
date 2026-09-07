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
    path = Path(
        "src/workflows/incident_resolution/"
        "workflow.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    observed = {}

    wanted = {
        "ProcedureTransitionExecutor",
        "AzureVmPostOperationObservationExecutor",
    }

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        function = node.func

        if not isinstance(
            function,
            ast.Name,
        ):
            continue

        if function.id not in wanted:
            continue

        observed[
            function.id
        ] = {
            keyword.arg:
                keyword.value
            for keyword
            in node.keywords
            if keyword.arg is not None
        }

    assert (
        "ProcedureTransitionExecutor"
        in observed
    )

    assert (
        "AzureVmPostOperationObservationExecutor"
        in observed
    )

    transition_keywords = (
        observed[
            "ProcedureTransitionExecutor"
        ]
    )

    observation_keywords = (
        observed[
            "AzureVmPostOperationObservationExecutor"
        ]
    )

    assert (
        "wait_recheck_consumption_ledger"
        in transition_keywords
    )

    assert (
        "wait_recheck_consumption_ledger"
        in observation_keywords
    )

    transition_value = (
        transition_keywords[
            "wait_recheck_consumption_ledger"
        ]
    )

    observation_value = (
        observation_keywords[
            "wait_recheck_consumption_ledger"
        ]
    )

    assert isinstance(
        transition_value,
        ast.Name,
    )

    assert isinstance(
        observation_value,
        ast.Name,
    )

    assert (
        transition_value.id
        == observation_value.id
        == "wait_recheck_ledger"
    )

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