import os

import pytest

from src.agents.contracts import (
    KnowledgeResult,
)
from src.agents.foundry_agents import (
    FoundryAgents,
)


@pytest.mark.asyncio
@pytest.mark.live
async def test_foundry_knowledge_live():
    if not os.environ.get(
        "FOUNDRY_PROJECT_ENDPOINT"
    ):
        pytest.skip(
            "FOUNDRY_PROJECT_ENDPOINT no configurado."
        )

    agents = FoundryAgents()

    prompt = """
Busca en el conocimiento corporativo disponible documentación relacionada con la siguiente incidencia:

AlertId: ALT-SQL-AG-001
Recurso: SQLPROD01
Tipo de recurso: Microsoft SQL Server Always On Availability Group
Incidencia: La réplica secundaria del Availability Group AG-PROD ha dejado de sincronizarse con la réplica primaria durante más de 10 minutos.

Recupera únicamente información respaldada por la base de conocimiento corporativa.

Devuelve exclusivamente la respuesta estructurada definida por tus instrucciones.
""".strip()

    result = await agents.run_knowledge(
        prompt
    )

    assert isinstance(
        result,
        KnowledgeResult,
    )

    assert (
        result.alert_id
        == "ALT-SQL-AG-001"
    )

    assert result.knowledge_found is True

    assert result.documents

    assert result.knowledge_summary is not None

    assert 0.0 < result.confidence <= 1.0

    document_ids = {
        document.id
        for document in result.documents
        if document.id is not None
    }

    assert (
        "NTTSY-PRO-016" in document_ids
        or "NTTSY-PRO-017" in document_ids
        or "NTTSY-PRO-020" in document_ids
    )