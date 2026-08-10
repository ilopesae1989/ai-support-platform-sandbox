import pytest
from pydantic import ValidationError

from src.agents.contracts import (
    KnowledgeResult,
)


def test_valid_knowledge_found():
    result = KnowledgeResult.model_validate(
        {
            "alert_id": "ALT-CPU-001",
            "knowledge_found": True,
            "documents": [
                {
                    "id": "NTTSY-PRO-017",
                    "name": (
                        "Revisión de infraestructura "
                        "de un servidor genérico"
                    ),
                    "version": "v1.3",
                    "relevance_summary": (
                        "Contiene información relacionada "
                        "con revisión de CPU."
                    ),
                }
            ],
            "knowledge_summary": (
                "La documentación contiene información "
                "relacionada con revisión de CPU."
            ),
            "limitations": [],
            "confidence": 0.88,
        }
    )

    assert result.knowledge_found is True
    assert len(result.documents) == 1
    assert (
        result.documents[0].id
        == "NTTSY-PRO-017"
    )


def test_valid_knowledge_not_found():
    result = KnowledgeResult.model_validate(
        {
            "alert_id": "ALT-QNT-001",
            "knowledge_found": False,
            "documents": [],
            "knowledge_summary": None,
            "limitations": [
                (
                    "No se ha encontrado información "
                    "validada aplicable."
                )
            ],
            "confidence": 0.0,
        }
    )

    assert result.knowledge_found is False
    assert result.documents == []
    assert result.knowledge_summary is None
    assert result.confidence == 0.0


def test_knowledge_found_requires_documents():
    with pytest.raises(ValidationError):
        KnowledgeResult.model_validate(
            {
                "alert_id": "ALT-001",
                "knowledge_found": True,
                "documents": [],
                "knowledge_summary": "Existe información.",
                "limitations": [],
                "confidence": 0.8,
            }
        )


def test_knowledge_not_found_requires_zero_confidence():
    with pytest.raises(ValidationError):
        KnowledgeResult.model_validate(
            {
                "alert_id": "ALT-001",
                "knowledge_found": False,
                "documents": [],
                "knowledge_summary": None,
                "limitations": [
                    "No encontrado."
                ],
                "confidence": 0.25,
            }
        )


def test_duplicate_document_ids_are_rejected():
    with pytest.raises(ValidationError):
        KnowledgeResult.model_validate(
            {
                "alert_id": "ALT-001",
                "knowledge_found": True,
                "documents": [
                    {
                        "id": "NTTSY-PRO-017",
                        "name": "Documento A",
                        "version": "v1.3",
                        "relevance_summary": "Relacionado.",
                    },
                    {
                        "id": "NTTSY-PRO-017",
                        "name": "Documento A duplicado",
                        "version": "v1.3",
                        "relevance_summary": "Relacionado.",
                    },
                ],
                "knowledge_summary": "Información encontrada.",
                "limitations": [],
                "confidence": 0.9,
            }
        )


def test_direct_procedure_query_can_have_null_alert_id():
    result = KnowledgeResult.model_validate(
        {
            "alert_id": None,
            "knowledge_found": True,
            "documents": [
                {
                    "id": "NTTSY-PRO-017",
                    "name": (
                        "Revisión de infraestructura "
                        "de un servidor genérico"
                    ),
                    "version": "v1.3",
                    "relevance_summary": (
                        "Procedimiento solicitado "
                        "explícitamente."
                    ),
                }
            ],
            "knowledge_summary": (
                "Se ha recuperado el procedimiento."
            ),
            "limitations": [],
            "confidence": 0.92,
        }
    )

    assert result.alert_id is None