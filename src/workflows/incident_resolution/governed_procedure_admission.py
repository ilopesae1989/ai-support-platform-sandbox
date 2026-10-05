from __future__ import annotations

from src.workflows.incident_resolution.procedure_admission import (
    ProcedureAdmission,
    ProcedureAdmissionError,
    ProcedureAdmissionPolicy,
)

from src.workflows.incident_resolution.procedure_governance import (
    ProcedureGovernanceApprovalPolicy,
)


class GovernedProcedureAdmissionPolicy:
    """
    Composición determinista de:

    - Procedure Admission;
    - Governance Approval.

    Orden autoritativo:

        identidad solicitada
            ↓
        ProcedureAdmissionPolicy
            ↓
        catalog
            → governance approval obligatoria

        legacy_compatibility
            → bridge explícito preservado

    Este gate:

    - no concede capability;
    - no concede HITL;
    - no resuelve owner;
    - no ejecuta rollback;
    - no cambia versión;
    - no hace fallback;
    - no ejecuta operaciones.
    """

    def __init__(
        self,
        *,
        admission_policy: ProcedureAdmissionPolicy,
        governance_policy: ProcedureGovernanceApprovalPolicy,
    ) -> None:
        if not isinstance(
            admission_policy,
            ProcedureAdmissionPolicy,
        ):
            raise TypeError(
                "admission_policy debe ser "
                "ProcedureAdmissionPolicy."
            )

        if not isinstance(
            governance_policy,
            ProcedureGovernanceApprovalPolicy,
        ):
            raise TypeError(
                "governance_policy debe ser "
                "ProcedureGovernanceApprovalPolicy."
            )

        self._admission_policy = (
            admission_policy
        )

        self._governance_policy = (
            governance_policy
        )

    def admit(
        self,
        *,
        procedure_id: str,
        procedure_version: str,
        procedure_name: str,
    ) -> ProcedureAdmission:
        admission = (
            self._admission_policy.admit(
                procedure_id=procedure_id,
                procedure_version=(
                    procedure_version
                ),
                procedure_name=procedure_name,
            )
        )

        if admission.source == "catalog":
            (
                self._governance_policy
                .require_governance_approval(
                    procedure_id=(
                        admission.procedure_id
                    ),
                    procedure_version=(
                        admission.procedure_version
                    ),
                )
            )

            return admission

        if (
            admission.source
            == "legacy_compatibility"
        ):
            return admission

        raise ProcedureAdmissionError(
            "ProcedureAdmission contiene "
            "source no soportado."
        )