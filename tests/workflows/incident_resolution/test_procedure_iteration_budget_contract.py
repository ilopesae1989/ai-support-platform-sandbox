import ast
import pathlib

import pytest

from pydantic import (
    ValidationError,
)

from src.agents.contracts import (
    ProcedureExecutionResult,
)

from tests.workflows.incident_resolution.test_incident_workflow_azure_operations import (
    AzureWorkflowFakeFoundryAgents,
)


FRAMEWORK_MAX_ITERATIONS = 100

INITIAL_TO_FIRST_HITL_ITERATIONS = 7

ITERATIONS_PER_ADDITIONAL_STEP = 11

FINAL_STEP_TAIL_ITERATIONS = 8


def _maximum_observed_iteration(
    total_steps: int,
) -> int:
    assert total_steps >= 1

    return (
        INITIAL_TO_FIRST_HITL_ITERATIONS
        + (
            ITERATIONS_PER_ADDITIONAL_STEP
            * (
                total_steps
                - 1
            )
        )
        + FINAL_STEP_TAIL_ITERATIONS
    )


def _total_steps_upper_bounds():
    field = (
        ProcedureExecutionResult
        .model_fields[
            "total_steps"
        ]
    )

    values = []

    for metadata in field.metadata:
        le = getattr(
            metadata,
            "le",
            None,
        )

        if le is not None:
            values.append(
                le
            )

    return values


def _workflow_max_iterations_keywords():
    import src.workflows.incident_resolution.workflow as workflow_module

    path = pathlib.Path(
        workflow_module.__file__
    )

    text = (
        path.read_text(
            encoding="utf-8"
        )
        .replace("\r\n", "\n")
    )

    tree = ast.parse(
        text,
        filename=str(path),
    )

    values = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "WorkflowBuilder"
        ):
            continue

        for keyword in node.keywords:
            if (
                keyword.arg
                != "max_iterations"
            ):
                continue

            values.append(
                keyword.value
            )

    return values


def test_certified_iteration_math_allows_eight_steps_but_not_nine():
    assert (
        _maximum_observed_iteration(
            5
        )
        == 59
    )

    assert (
        _maximum_observed_iteration(
            8
        )
        == 92
    )

    assert (
        _maximum_observed_iteration(
            9
        )
        == 103
    )

    assert (
        _maximum_observed_iteration(
            8
        )
        < FRAMEWORK_MAX_ITERATIONS
    )

    assert (
        _maximum_observed_iteration(
            9
        )
        >= FRAMEWORK_MAX_ITERATIONS
    )


def test_procedure_execution_result_caps_total_steps_at_eight():
    assert (
        _total_steps_upper_bounds()
        == [8]
    )


@pytest.mark.asyncio
async def test_procedure_execution_result_accepts_eight_steps_and_rejects_nine():
    agents = (
        AzureWorkflowFakeFoundryAgents()
    )

    baseline = (
        await agents
        .run_procedure_execution(
            "iteration budget probe"
        )
    )

    payload = baseline.model_dump(
        mode="python"
    )

    payload[
        "total_steps"
    ] = 8

    payload[
        "current_step"
    ] = 1

    accepted = (
        ProcedureExecutionResult
        .model_validate(
            payload
        )
    )

    assert (
        accepted.total_steps
        == 8
    )

    payload[
        "total_steps"
    ] = 9

    with pytest.raises(
        ValidationError,
    ):
        (
            ProcedureExecutionResult
            .model_validate(
                payload
            )
        )


def test_incident_resolution_workflow_explicitly_pins_max_iterations_to_100():
    values = (
        _workflow_max_iterations_keywords()
    )

    assert len(
        values
    ) == 1

    value = (
        values[0]
    )

    assert isinstance(
        value,
        ast.Constant,
    )

    assert value.value == 100
