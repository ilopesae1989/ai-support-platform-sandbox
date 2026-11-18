from __future__ import annotations

from dataclasses import (
    dataclass,
)

from agent_framework import (
    WorkflowContext,
)

from .alert_models import (
    NormalizedAlert,
)


INCIDENT_CONVERSATION_ID_STATE_KEY = (
    "incident_conversation_id"
)


def _require_exact_conversation_id(
    value: object,
) -> str:
    """
    Valida correlación de transporte.

    No normaliza.
    No deriva.
    No concede autoridad operacional.
    """

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            "conversation_id debe ser str."
        )

    if (
        not value
        or not value.strip()
    ):
        raise ValueError(
            "conversation_id no puede estar vacío."
        )

    if value != value.strip():
        raise ValueError(
            "conversation_id no puede requerir "
            "normalización."
        )

    return value


@dataclass(
    frozen=True,
)
class IncidentWorkflowInput:
    """
    Input replayable de incident-resolution.

    Sólo contiene:

    - NormalizedAlert autoritativa;
    - correlation de transporte Teams.

    No contiene identidad del operador,
    autorización ni autoridad operacional.
    """

    alert: NormalizedAlert
    conversation_id: str

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.alert,
            NormalizedAlert,
        ):
            raise TypeError(
                "alert debe ser NormalizedAlert."
            )

        _require_exact_conversation_id(
            self.conversation_id
        )


@dataclass(frozen=True)
class AdmittedIncidentWorkflowInput(IncidentWorkflowInput):
    """Trusted host input; separate from the unchanged channel transport envelope."""

    execution_id: str

    def __post_init__(self):
        super().__post_init__()
        from src.runtime.execution_affinity import require_identifier
        require_identifier(self.execution_id, "execution_id")


def incident_input_fingerprint(workflow_input: IncidentWorkflowInput) -> str:
    """Bind the admitted alert and transport correlation, excluding the record ID."""
    from src.runtime.execution_affinity import canonical_digest
    return canonical_digest({"alert": workflow_input.alert.model_dump(mode="json"),
                             "conversation_id": workflow_input.conversation_id})


def admit_incident_workflow_input(*, alert, conversation_id, execution_store) -> AdmittedIncidentWorkflowInput:
    """Trusted host admission, committed before workflow.run creates its entry checkpoint.

    A new invocation creates a distinct execution, as in the historical identity
    contract. This is not alert deduplication or permission to replay an execution.
    """
    from src.runtime.incident_execution import IncidentExecutionStore
    from src.runtime.procedure.identity import create_workflow_id
    if not isinstance(execution_store, IncidentExecutionStore):
        raise TypeError("Explicit execution persistence required.")
    result = AdmittedIncidentWorkflowInput(alert=alert, conversation_id=conversation_id,
                                   execution_id=create_workflow_id())
    execution_store.admit(execution_id=result.execution_id, input_sha256=incident_input_fingerprint(result))
    return result


def store_incident_conversation_id(
    ctx: WorkflowContext,
    conversation_id: str,
) -> None:
    """
    Guarda únicamente correlación de transporte
    como workflow state JSON-native.
    """

    exact = (
        _require_exact_conversation_id(
            conversation_id
        )
    )

    ctx.set_state(
        INCIDENT_CONVERSATION_ID_STATE_KEY,
        exact,
    )


def load_incident_conversation_id(
    ctx: WorkflowContext,
) -> str | None:
    """
    Devuelve correlación durable exacta.

    None mantiene compatibilidad con workflows
    iniciados directamente mediante NormalizedAlert.
    """

    value = ctx.get_state(
        INCIDENT_CONVERSATION_ID_STATE_KEY,
        None,
    )

    if value is None:
        return None

    return (
        _require_exact_conversation_id(
            value
        )
    )
