from __future__ import annotations

from src.runtime.procedure.identity import (
    create_operation_id,
)

from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)

from .azure_operations_models import (
    AzureOperationRequest,
    VerifiedAzureOperationRequest,
)


class PreCallSecurityError(ValueError):
    pass


class PreCallSecurityVerifier:
    _SECURITY_FIELDS = (
        "operation_id",
        "workflow_id",
        "approval_id",
        "alert_id",
        "correlation_id",
        "conversation_id",
        "procedure_id",
        "procedure_version",
        "current_step",
        "step_id",
        "description",
        "operation_domain",
        "operation_kind",
        "operation_action",
        "next_action",
        "target_resource",
        "required_parameters",
        "resolved_parameters",
    )

    @staticmethod
    def _validate_parameter_binding(
        *,
        required_parameters: list[str],
        resolved_parameters,
        source_description: str,
    ) -> None:
        required = list(
            required_parameters
        )

        resolved_names = [
            parameter.name
            for parameter
            in resolved_parameters
        ]

        if (
            len(required)
            != len(set(required))
        ):
            raise PreCallSecurityError(
                f"{source_description} contiene "
                "required_parameters duplicados."
            )

        if (
            len(resolved_names)
            != len(set(resolved_names))
        ):
            raise PreCallSecurityError(
                f"{source_description} contiene "
                "resolved_parameters duplicados."
            )

        if required != resolved_names:
            raise PreCallSecurityError(
                f"{source_description}: "
                "required_parameters y "
                "resolved_parameters no coinciden "
                "exactamente."
            )

        for parameter in resolved_parameters:
            if parameter.name == "":
                raise PreCallSecurityError(
                    f"{source_description} contiene "
                    "un parámetro sin nombre."
                )

            if parameter.value == "":
                raise PreCallSecurityError(
                    f"{source_description} contiene "
                    "un parámetro sin valor."
                )

            if parameter.source == "":
                raise PreCallSecurityError(
                    f"{source_description} contiene "
                    "un parámetro sin source."
                )

    @classmethod
    def _validate_approved_step(
        cls,
        step: ApprovedProcedureStep,
    ) -> None:
        if step.approved is not True:
            raise PreCallSecurityError(
                "ApprovedProcedureStep no está "
                "aprobado."
            )

        if not step.approval_id:
            raise PreCallSecurityError(
                "ApprovedProcedureStep no contiene "
                "approval_id."
            )

        if (
            not step.description
            or not step.description.strip()
        ):
            raise PreCallSecurityError(
                "ApprovedProcedureStep no contiene "
                "description válida."
            )

        if (
            step.operation_domain
            != "azure"
        ):
            raise PreCallSecurityError(
                "ApprovedProcedureStep no pertenece "
                "exactamente al dominio azure."
            )

        if (
            step.next_action
            != NextAction.EXECUTE_STEP
        ):
            raise PreCallSecurityError(
                "ApprovedProcedureStep no contiene "
                "next_action=execute_step."
            )

        if step.operation_kind not in {
            OperationKind.READ,
            OperationKind.WRITE,
        }:
            raise PreCallSecurityError(
                "ApprovedProcedureStep contiene "
                "un operation_kind no permitido."
            )

        cls._validate_parameter_binding(
            required_parameters=(
                step.required_parameters
            ),

            resolved_parameters=(
                step.resolved_parameters
            ),

            source_description=(
                "ApprovedProcedureStep"
            ),
        )

    @classmethod
    def _validate_candidate(
        cls,
        candidate: AzureOperationRequest,
    ) -> None:
        if not candidate.operation_id:
            raise PreCallSecurityError(
                "AzureOperationRequest no contiene "
                "operation_id."
            )

        if not candidate.approval_id:
            raise PreCallSecurityError(
                "AzureOperationRequest no contiene "
                "approval_id."
            )

        if (
            not candidate.description
            or not candidate.description.strip()
        ):
            raise PreCallSecurityError(
                "AzureOperationRequest no contiene "
                "description válida."
            )

        if (
            candidate.operation_domain
            != "azure"
        ):
            raise PreCallSecurityError(
                "AzureOperationRequest no pertenece "
                "exactamente al dominio azure."
            )

        if (
            candidate.next_action
            != NextAction.EXECUTE_STEP
        ):
            raise PreCallSecurityError(
                "AzureOperationRequest no contiene "
                "next_action=execute_step."
            )

        if candidate.operation_kind not in {
            OperationKind.READ,
            OperationKind.WRITE,
        }:
            raise PreCallSecurityError(
                "AzureOperationRequest contiene "
                "un operation_kind no permitido."
            )

        cls._validate_parameter_binding(
            required_parameters=(
                candidate.required_parameters
            ),

            resolved_parameters=(
                candidate.resolved_parameters
            ),

            source_description=(
                "AzureOperationRequest"
            ),
        )

    @staticmethod
    def _build_expected_request(
        step: ApprovedProcedureStep,
    ) -> AzureOperationRequest:
        operation_id = (
            create_operation_id(
                workflow_id=(
                    step.workflow_id
                ),

                approval_id=(
                    step.approval_id
                ),

                alert_id=(
                    step.alert_id
                ),

                procedure_id=(
                    step.procedure_id
                ),

                current_step=(
                    step.current_step
                ),

                step_id=(
                    step.step_id
                ),
            )
        )

        return AzureOperationRequest(
            operation_id=(
                operation_id
            ),

            workflow_id=(
                step.workflow_id
            ),

            approval_id=(
                step.approval_id
            ),

            alert_id=(
                step.alert_id
            ),

            correlation_id=(
                step.correlation_id
            ),

            conversation_id=(
                step.conversation_id
            ),

            procedure_id=(
                step.procedure_id
            ),

            procedure_version=(
                step.procedure_version
            ),

            current_step=(
                step.current_step
            ),

            step_id=(
                step.step_id
            ),

            description=(
                step.description
            ),

            operation_domain=(
                step.operation_domain
            ),

            operation_kind=(
                step.operation_kind
            ),

            operation_action=(
                step.operation_action
            ),

            next_action=(
                step.next_action
            ),

            target_resource=(
                step.target_resource
            ),

            required_parameters=list(
                step.required_parameters
            ),

            resolved_parameters=[
                parameter.model_copy(
                    deep=True
                )
                for parameter
                in step.resolved_parameters
            ],
        )

    @classmethod
    def verify(
        cls,
        *,
        approved_step: ApprovedProcedureStep,
        candidate: AzureOperationRequest,
    ) -> VerifiedAzureOperationRequest:
        cls._validate_approved_step(
            approved_step
        )

        cls._validate_candidate(
            candidate
        )

        expected = (
            cls._build_expected_request(
                approved_step
            )
        )

        changed_fields = [
            field_name
            for field_name
            in cls._SECURITY_FIELDS
            if (
                getattr(
                    candidate,
                    field_name,
                )
                != getattr(
                    expected,
                    field_name,
                )
            )
        ]

        if changed_fields:
            raise PreCallSecurityError(
                "La operación Azure candidata "
                "no coincide exactamente con "
                "la operación aprobada. "
                "Campos distintos: "
                + ", ".join(
                    changed_fields
                )
            )

        return (
            VerifiedAzureOperationRequest
            .model_validate(
                {
                    **candidate.model_dump(
                        mode="python"
                    ),

                    "security_verified":
                        True,

                    "verification_source":
                        (
                            "pre_call_security_verifier"
                        ),
                }
            )
        )