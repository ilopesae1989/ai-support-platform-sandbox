from __future__ import annotations

from src.agents.contracts import (
    ClassificationResult,
    KnowledgeResult,
)

from src.workflows.incident_resolution.alert_models import (
    NormalizedAlert,
)

from src.workflows.incident_resolution.models import (
    ClassifiedAlertContext,
    KnowledgeEnrichedAlertContext,
)

from src.workflows.incident_resolution.executors.knowledge import (
    KnowledgeExecutor,
)

from src.workflows.incident_resolution.executors.triage import (
    AlertTriageExecutor,
)


TDD_MARKER = (
    "TDD_PHASE18_COGNITIVE_INCIDENT_ORIGIN_PROMPT_RED"
)


FACTUAL_RULE = (
    "incident_origin describe únicamente "
    "la procedencia factual del incidente."
)

NO_AUTHORITY_RULE = (
    "No concede autorización de ejecución."
)


def _alert(
    incident_origin: str,
) -> NormalizedAlert:

    return NormalizedAlert(
        alert_id="ALT-COGNITIVE-ORIGIN-001",

        source="azure_monitor",

        incident_origin=(
            incident_origin
        ),

        source_event_id=(
            "synthetic-event-001"
        ),

        name=(
            "Azure VM stopped"
        ),

        description=(
            "La máquina virtual se encuentra "
            "detenida."
        ),

        source_severity="Critical",

        affected_resource="vm-test-01",

        resource_type=(
            "Microsoft.Compute/"
            "virtualMachines"
        ),

        service=(
            "Azure Virtual Machines"
        ),

        environment="sandbox",

        subscription_id=(
            "sub-test-001"
        ),

        resource_group="rg-test",

        vm_name="vm-test-01",

        tenant_id=None,

        correlation_id=(
            "corr-origin-001"
        ),

        raw_attributes={
            "incident_origin":
                "observed",

            "native_secret":
                "must-not-leak",
        },
    )


def _classification(
) -> ClassificationResult:

    return ClassificationResult.model_validate(
        {
            "alert_id":
                "ALT-COGNITIVE-ORIGIN-001",

            "alert_classification":
                "azure_vm_stopped_allocated",

            "technical_domain":
                "azure",

            "affected_resource":
                "vm-test-01",

            "affected_service":
                "Azure Virtual Machines",

            "classification_summary":
                "VM stopped.",

            "requires_clarification":
                False,

            "missing_information":
                [],

            "confidence":
                0.95,
        }
    )


def _knowledge(
) -> KnowledgeResult:

    return KnowledgeResult.model_validate(
        {
            "alert_id":
                "ALT-COGNITIVE-ORIGIN-001",

            "knowledge_found":
                True,

            "documents": [
                {
                    "id":
                        "NTTSY-SBX-AZ-VM-DEMO-001",

                    "name":
                        "Synthetic VM demo procedure",

                    "version":
                        "1.0",

                    "relevance_summary":
                        "Synthetic demo procedure.",
                },
            ],

            "knowledge_summary":
                "Synthetic procedure available.",

            "limitations":
                [],

            "confidence":
                0.95,
        }
    )


def _classified(
    incident_origin: str,
) -> ClassifiedAlertContext:

    return ClassifiedAlertContext(
        alert=_alert(
            incident_origin
        ),

        classification=(
            _classification()
        ),
    )


def _enriched(
    incident_origin: str,
) -> KnowledgeEnrichedAlertContext:

    return KnowledgeEnrichedAlertContext(
        alert=_alert(
            incident_origin
        ),

        classification=(
            _classification()
        ),

        knowledge=(
            _knowledge()
        ),
    )


def test_knowledge_prompt_exposes_synthetic_demo_origin():
    prompt = (
        KnowledgeExecutor
        ._build_prompt(
            _classified(
                "synthetic_demo"
            )
        )
    )

    assert (
        "incident_origin: synthetic_demo"
        in prompt
    )


def test_triage_prompt_exposes_synthetic_demo_origin():
    prompt = (
        AlertTriageExecutor
        ._build_prompt(
            _enriched(
                "synthetic_demo"
            )
        )
    )

    assert (
        "incident_origin: synthetic_demo"
        in prompt
    )


def test_knowledge_prompt_exposes_observed_origin():
    prompt = (
        KnowledgeExecutor
        ._build_prompt(
            _classified(
                "observed"
            )
        )
    )

    assert (
        "incident_origin: observed"
        in prompt
    )


def test_triage_prompt_exposes_observed_origin():
    prompt = (
        AlertTriageExecutor
        ._build_prompt(
            _enriched(
                "observed"
            )
        )
    )

    assert (
        "incident_origin: observed"
        in prompt
    )


def test_knowledge_prompt_frames_origin_as_factual_not_authority():
    prompt = (
        KnowledgeExecutor
        ._build_prompt(
            _classified(
                "synthetic_demo"
            )
        )
    )

    assert FACTUAL_RULE in prompt
    assert NO_AUTHORITY_RULE in prompt


def test_triage_prompt_frames_origin_as_factual_not_authority():
    prompt = (
        AlertTriageExecutor
        ._build_prompt(
            _enriched(
                "synthetic_demo"
            )
        )
    )

    assert FACTUAL_RULE in prompt
    assert NO_AUTHORITY_RULE in prompt


def test_cognitive_prompts_do_not_leak_raw_attributes():
    knowledge_prompt = (
        KnowledgeExecutor
        ._build_prompt(
            _classified(
                "synthetic_demo"
            )
        )
    )

    triage_prompt = (
        AlertTriageExecutor
        ._build_prompt(
            _enriched(
                "synthetic_demo"
            )
        )
    )

    for prompt in (
        knowledge_prompt,
        triage_prompt,
    ):
        assert (
            "native_secret"
            not in prompt
        )

        assert (
            "must-not-leak"
            not in prompt
        )


def test_raw_attributes_cannot_override_typed_origin():
    classified = (
        _classified(
            "synthetic_demo"
        )
    )

    enriched = (
        _enriched(
            "synthetic_demo"
        )
    )

    assert (
        classified.alert.incident_origin
        == "synthetic_demo"
    )

    assert (
        enriched.alert.incident_origin
        == "synthetic_demo"
    )

    assert (
        classified
        .alert
        .raw_attributes[
            "incident_origin"
        ]
        == "observed"
    )

    assert (
        enriched
        .alert
        .raw_attributes[
            "incident_origin"
        ]
        == "observed"
    )