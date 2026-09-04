import ast
import json
import pathlib
import re

import pytest

import src.workflows.incident_resolution.workflow as workflow_module

from src.workflows.incident_resolution.workflow import (
    build_incident_resolution_workflow,
)

from tests.workflows.incident_resolution.test_incident_workflow import (
    create_alert,
)

from tests.workflows.incident_resolution.test_phase17_boundary import (
    Phase17BoundaryFakeFoundryAgents,
)


def _read_workflow_source():
    path = pathlib.Path(
        workflow_module.__file__
    )

    text = (
        path.read_text(
            encoding="utf-8"
        )
        .replace("\r\n", "\n")
    )

    return (
        text,
        ast.parse(
            text,
            filename=str(path),
        ),
    )


def _call_name(
    node,
):
    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):
        prefix = _call_name(
            node.value
        )

        if prefix:
            return (
                prefix
                + "."
                + node.attr
            )

        return node.attr

    return None


def _exact_continuation_loop_edges():
    text, tree = (
        _read_workflow_source()
    )

    matches = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not (
            isinstance(
                node.func,
                ast.Attribute,
            )
            and node.func.attr
            == "add_edge"
            and len(node.args) >= 2
        ):
            continue

        source = (
            ast.get_source_segment(
                text,
                node.args[0],
            )
            or ""
        ).strip()

        target = (
            ast.get_source_segment(
                text,
                node.args[1],
            )
            or ""
        ).strip()

        if (
            source
            == "procedure_transition"
            and target
            == "procedure"
        ):
            matches.append(
                node
            )

    return matches


def _assert_exact_continuation_loop_edge():
    matches = (
        _exact_continuation_loop_edges()
    )

    assert len(matches) == 1


def _find_requested_step(
    value,
):
    if isinstance(
        value,
        dict,
    ):
        if "requested_step" in value:
            requested_step = (
                value[
                    "requested_step"
                ]
            )

            if isinstance(
                requested_step,
                bool,
            ):
                raise AssertionError(
                    "requested_step no puede ser bool."
                )

            return int(
                requested_step
            )

        found = []

        for child in value.values():
            result = (
                _find_requested_step(
                    child
                )
            )

            if result is not None:
                found.append(
                    result
                )

        if not found:
            return None

        if len(
            set(found)
        ) != 1:
            raise AssertionError(
                "requested_step ambiguo."
            )

        return found[0]

    if isinstance(
        value,
        list,
    ):
        found = []

        for child in value:
            result = (
                _find_requested_step(
                    child
                )
            )

            if result is not None:
                found.append(
                    result
                )

        if not found:
            return None

        if len(
            set(found)
        ) != 1:
            raise AssertionError(
                "requested_step ambiguo."
            )

        return found[0]

    return None


class TwoStepContinuationFakeFoundryAgents(
    Phase17BoundaryFakeFoundryAgents
):
    """
    Fake exclusivo para demostrar el wiring N+1.

    Respeta requested_step procedente de Python.

    No decide el cursor.
    No ejecuta servicios reales.
    """

    def __init__(
        self,
    ):
        super().__init__(
            validation_status="satisfied",
            proposed_next_action="continue",
        )

        self.requested_steps = []

    async def run_procedure_execution(
        self,
        message: str,
        *,
        agent_version: str | None = None,
    ):
        #
        # Phase17BoundaryFakeFoundryAgents ya:
        #
        # - observa requested_step desde el prompt;
        # - registra requested_steps;
        # - alinea current_step y step.id.
        #
        # Este fake sólo convierte el procedimiento
        # en un escenario autoritativo de dos pasos.
        #
        result = (
            await super()
            .run_procedure_execution(
                message,
                agent_version=agent_version,
            )
        )

        payload = result.model_dump(
            mode="python"
        )

        payload[
            "total_steps"
        ] = 2

        return type(
            result
        ).model_validate(
            payload
        )


def test_workflow_declares_exact_procedure_transition_to_procedure_edge():
    _assert_exact_continuation_loop_edge()


@pytest.mark.asyncio
async def test_continue_enters_step_two_and_requires_fresh_hitl_before_second_operation():
    #
    # Este assert garantiza que el test de
    # comportamiento sólo puede pasar cuando
    # el grafo productivo contiene el loop.
    #
    _assert_exact_continuation_loop_edge()

    agents = (
        TwoStepContinuationFakeFoundryAgents()
    )

    workflow = (
        build_incident_resolution_workflow(
            agents=agents,
        )
    )

    first_hitl = {}

    async for event in workflow.run(
        create_alert(),
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            first_hitl[
                event.request_id
            ] = True

    assert len(
        first_hitl
    ) == 1

    first_request_ids = set(
        first_hitl
    )

    assert (
        agents.requested_steps
        == [1]
    )

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
    ]

    second_hitl_events = []
    outputs = []

    async for event in workflow.run(
        responses=first_hitl,
        stream=True,
    ):
        if (
            event.type
            == "request_info"
        ):
            second_hitl_events.append(
                event
            )

        if (
            event.type
            == "output"
        ):
            outputs.append(
                event.data
            )

    #
    # Step 1 termina y CONTINUE vuelve a
    # Procedure para pedir exactamente N+1.
    #
    assert (
        agents.requested_steps
        == [1, 2]
    )

    assert (
        agents.calls.count(
            "procedure_execution"
        )
        == 2
    )

    #
    # Sólo la operación del step 1 se ha
    # ejecutado. El step 2 queda detenido en
    # un HITL nuevo.
    #
    assert (
        agents.calls.count(
            "azure_operations"
        )
        == 1
    )

    assert (
        agents.calls.count(
            "procedure_validation"
        )
        == 1
    )

    assert len(
        second_hitl_events
    ) == 1

    second_request_id = (
        second_hitl_events[0]
        .request_id
    )

    assert (
        second_request_id
        not in first_request_ids
    )

    #
    # CONTINUE no produce salida terminal:
    # el workflow ha continuado hasta el nuevo
    # boundary humano.
    #
    assert outputs == []

    assert agents.calls == [
        "classification",
        "knowledge",
        "alert_triage",
        "procedure_execution",
        "azure_operations",
        "procedure_validation",
        "procedure_execution",
    ]
