import os

import pytest

from src.agents.catalog import AgentKey
from src.agents.foundry_agents import FoundryAgents
from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)


def create_exact_candidate_alert() -> NormalizedAlert:
    """
    Candidato LIVE para comprobar si el conocimiento
    corporativo permite clasificar un caso SQL AlwaysOn
    como procedure_match=exact.

    Este probe NO ejecuta Procedure Execution,
    Runtime ni operaciones técnicas.
    """

    return NormalizedAlert(
        alert_id="ALT-SQL-ALWAYSON-ROLE-001",
        source="scom",
        source_event_id="SCOM-LIVE-ALWAYSON-ROLE-001",
        name="SQL AlwaysOn Role Change",
        description=(
            "SCOM ha generado una alerta de cambio de rol "
            "de SQL Server Always On para el Availability "
            "Group AG-PROD en SQLPROD01."
        ),
        source_severity="Critical",
        affected_resource="SQLPROD01",
        resource_type=(
            "Microsoft SQL Server Always On "
            "Availability Group"
        ),
        service=(
            "Microsoft SQL Server Always On "
            "Availability Group"
        ),
        environment="production",
        correlation_id=(
            "corr-live-alwayson-role-001"
        ),
        raw_attributes={
            "live_test_marker":
                "must-not-be-used-for-routing"
        },
    )


def build_classification_prompt(
    alert: NormalizedAlert,
) -> str:
    return f"""
Clasifica la siguiente alerta.

AlertId: {alert.alert_id}
Origen: {alert.source}
Nombre: {alert.name}
Severidad origen: {alert.source_severity}
Recurso: {alert.affected_resource}
Tipo de recurso: {alert.resource_type}
Servicio: {alert.service}

Descripción:
{alert.description}

Devuelve únicamente la respuesta estructurada
definida por tu contrato.
""".strip()


def build_knowledge_prompt(
    alert: NormalizedAlert,
    classification,
) -> str:
    return f"""
Recupera conocimiento corporativo aplicable
a la siguiente alerta.

AlertId: {alert.alert_id}

Clasificación:
alert_classification:
{classification.alert_classification}

technical_domain:
{classification.technical_domain}

affected_resource:
{classification.affected_resource}

affected_service:
{classification.affected_service}

Descripción:
{alert.description}

Utiliza exclusivamente el conocimiento
corporativo disponible.

Devuelve únicamente la respuesta estructurada
definida por tu contrato.
""".strip()


def build_triage_prompt(
    alert: NormalizedAlert,
    classification,
    knowledge,
) -> str:
    documents = "\n".join(
        (
            f"- {document.id} — "
            f"{document.name} "
            f"{document.version}: "
            f"{document.relevance_summary}"
        )
        for document in knowledge.documents
    )

    limitations = "\n".join(
        f"- {item}"
        for item in knowledge.limitations
    )

    return f"""
Analiza la siguiente alerta.

Origen: {alert.source}
AlertId: {alert.alert_id}
Nombre: {alert.name}
Severidad origen: {alert.source_severity}
Recurso: {alert.affected_resource}
Tipo de recurso: {alert.resource_type}

Descripción:
{alert.description}

Clasificación previa:

alert_classification:
{classification.alert_classification}

technical_domain:
{classification.technical_domain}

affected_resource:
{classification.affected_resource}

affected_service:
{classification.affected_service}

Conocimiento corporativo recuperado:

{documents}

Limitaciones del conocimiento recuperado:

{limitations or "- Ninguna"}

Clasifica la alerta utilizando exclusivamente
los procedimientos y matrices corporativas
disponibles.

Devuelve únicamente la respuesta estructurada
definida por tus instrucciones.
""".strip()


@pytest.mark.asyncio
@pytest.mark.live
async def test_exact_candidate_live_probe():
    """
    Probe LIVE:

    NormalizedAlert
        ↓
    Classification REAL
        ↓
    Knowledge REAL
        ↓
    Triage REAL

    El test termina aquí deliberadamente.

    No llama Procedure Execution.
    No llega a Runtime.
    No ejecuta operaciones.
    """

    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT "
            "no configurado."
        )

    agents = FoundryAgents()

    #
    # Baseline congelada.
    #

    assert (
        agents.get_definition(
            AgentKey.CLASSIFICATION
        ).version
        == "7"
    )

    assert (
        agents.get_definition(
            AgentKey.KNOWLEDGE
        ).version
        == "8"
    )

    assert (
        agents.get_definition(
            AgentKey.ALERT_TRIAGE
        ).version
        == "10"
    )

    assert (
        agents.get_definition(
            AgentKey.PROCEDURE_EXECUTION
        ).version
        == "6"
    )

    alert = create_exact_candidate_alert()

    #
    # Classification REAL.
    #

    classification = (
        await agents.run_classification(
            build_classification_prompt(
                alert
            )
        )
    )

    print()
    print("=" * 80)
    print("CLASSIFICATION")
    print("=" * 80)
    print(classification)

    #
    # Knowledge REAL.
    #

    knowledge = (
        await agents.run_knowledge(
            build_knowledge_prompt(
                alert,
                classification,
            )
        )
    )

    print()
    print("=" * 80)
    print("KNOWLEDGE")
    print("=" * 80)
    print(knowledge)

    #
    # Triage REAL.
    #

    triage = (
        await agents.run_alert_triage(
            build_triage_prompt(
                alert,
                classification,
                knowledge,
            )
        )
    )

    print()
    print("=" * 80)
    print("TRIAGE")
    print("=" * 80)
    print(triage)

    print()
    print("=" * 80)
    print("DECISIÓN")
    print("=" * 80)

    print(
        "procedure_found =",
        triage.procedure_found,
    )

    print(
        "procedure_match =",
        triage.procedure_match,
    )

    print(
        "execution_eligible =",
        triage.execution_eligible,
    )

    print(
        "recommended_next_step =",
        triage.recommended_next_step,
    )

    print(
        "procedure =",
        triage.procedure,
    )

    print(
        "confidence =",
        triage.confidence,
    )

    print(
        "missing_context =",
        triage.missing_context,
    )

    #
    # Gates estructurales.
    #
    # NO obligamos todavía a que sea exact.
    # Queremos observar qué decide realmente
    # el pipeline.
    #

    assert classification.alert_id == (
        alert.alert_id
    )

    assert knowledge.alert_id == (
        alert.alert_id
    )

    assert triage.affected_resource == (
        alert.affected_resource
    )

    assert triage.procedure_match in {
        "exact",
        "partial",
        "none",
    }