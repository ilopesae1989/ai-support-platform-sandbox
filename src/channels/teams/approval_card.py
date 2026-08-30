from __future__ import annotations

from microsoft_teams.cards import (
    ActionSet,
    AdaptiveCard,
    ExecuteAction,
    SubmitData,
    TextBlock,
)

from src.runtime.procedure.workflow import (
    ApprovalRequest,
)


class TeamsApprovalCardError(
    ValueError
):
    pass


def _find_resolved_parameter(
    request: ApprovalRequest,
    name: str,
) -> str:
    matches = [
        parameter.value
        for parameter
        in request.resolved_parameters
        if parameter.name == name
    ]

    if len(matches) != 1:
        return "No disponible"

    return matches[0]


def build_teams_approval_card(
    request: ApprovalRequest,
) -> AdaptiveCard:
    """
    Renderiza exclusivamente la snapshot HITL
    congelada por Python.

    La tarjeta puede MOSTRAR autoridad operacional,
    pero sus acciones sólo DEVUELVEN:

        approval_id
        decision

    Nunca se devuelve desde Action.Execute:

        workflow_id
        procedure_id
        capability_id
        operation_action
        target_resource
        parámetros
        identidad del operador
    """

    if not isinstance(
        request,
        ApprovalRequest,
    ):
        raise TypeError(
            "request debe ser ApprovalRequest."
        )

    if not request.approval_id:
        raise TeamsApprovalCardError(
            "ApprovalRequest no contiene approval_id."
        )

    subscription_id = (
        _find_resolved_parameter(
            request,
            "subscription_id",
        )
    )

    resource_group = (
        _find_resolved_parameter(
            request,
            "resource_group",
        )
    )

    vm_name = (
        _find_resolved_parameter(
            request,
            "vm_name",
        )
    )

    operation_action = (
        request.operation_action
        or "No disponible"
    )

    capability_id = (
        request.capability_id
        or "No disponible"
    )

    target_resource = (
        request.target_resource
        or "No disponible"
    )

    procedure_version = (
        request.procedure_version
        or "No disponible"
    )

    body = [
        TextBlock(
            text="Aprobación requerida",
            weight="Bolder",
            size="Large",
            wrap=True,
        ),

        TextBlock(
            text=(
                "Se solicita autorización humana "
                "antes de ejecutar una operación "
                "externa."
            ),
            wrap=True,
        ),

        TextBlock(
            text=f"**Alerta:** {request.alert_id}",
            wrap=True,
        ),

        TextBlock(
            text=f"**Recurso:** {target_resource}",
            wrap=True,
        ),

        TextBlock(
            text=f"**VM:** {vm_name}",
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Subscription:** "
                f"{subscription_id}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Resource Group:** "
                f"{resource_group}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Procedimiento:** "
                f"{request.procedure_id}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Versión / Step:** "
                f"{procedure_version} / "
                f"{request.step_id}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Dominio / Tipo:** "
                f"{request.operation_domain} / "
                f"{request.operation_kind}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Operación:** "
                f"{operation_action}"
            ),
            wrap=True,
        ),

        TextBlock(
            text=(
                "**Capability:** "
                f"{capability_id}"
            ),
            wrap=True,
        ),

        TextBlock(
            text="**Operación exacta aprobable:**",
            weight="Bolder",
            wrap=True,
        ),

        TextBlock(
            text=request.description,
            wrap=True,
        ),

        ActionSet(
            actions=[
                (
                    ExecuteAction(
                        title="APROBAR"
                    )
                    .with_data(
                        SubmitData(
                            "approval_decision",
                            {
                                "approval_id":
                                    request.approval_id,

                                "decision":
                                    "approve",
                            },
                        )
                    )
                    .with_associated_inputs(
                        "none"
                    )
                ),

                (
                    ExecuteAction(
                        title="RECHAZAR"
                    )
                    .with_data(
                        SubmitData(
                            "approval_decision",
                            {
                                "approval_id":
                                    request.approval_id,

                                "decision":
                                    "reject",
                            },
                        )
                    )
                    .with_associated_inputs(
                        "none"
                    )
                ),
            ]
        ),
    ]

    return AdaptiveCard(
        version="1.5",
        body=body,
    )