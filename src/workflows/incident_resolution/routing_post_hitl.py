from src.runtime.procedure.models import (
    ApprovedProcedureStep,
    NextAction,
    OperationKind,
)


SUPPORTED_OPERATION_DOMAINS = frozenset(
    {
        "azure",
        "database",
        "itsm",
        "windows",
        "linux",
        "networking",
        "microsoft365",
    }
)


ROUTABLE_OPERATION_KINDS = frozenset(
    {
        OperationKind.READ,
        OperationKind.WRITE,
        OperationKind.HUMAN,
    }
)


def is_post_hitl_routable(
    step: ApprovedProcedureStep,
) -> bool:
    """
    Gate común de seguridad post-HITL.

    Ningún LLM participa aquí.

    Solo permite routing cuando:

    - existe aprobación explícita;
    - next_action es EXECUTE_STEP;
    - el dominio es conocido;
    - el tipo de operación está autorizado
      para entrar en routing operativo.
    """

    if step.approved is not True:
        return False

    if (
        step.next_action
        != NextAction.EXECUTE_STEP
    ):
        return False

    if (
        step.operation_domain
        not in SUPPORTED_OPERATION_DOMAINS
    ):
        return False

    if (
        step.operation_kind
        not in ROUTABLE_OPERATION_KINDS
    ):
        return False

    return True


def route_to_azure_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "azure"
    )


def route_to_database_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "database"
    )


def route_to_itsm_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "itsm"
    )


def route_to_windows_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "windows"
    )


def route_to_linux_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "linux"
    )


def route_to_networking_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "networking"
    )


def route_to_microsoft365_operation(
    step: ApprovedProcedureStep,
) -> bool:
    return (
        is_post_hitl_routable(step)
        and step.operation_domain == "microsoft365"
    )


def route_to_blocked_operation(
    step: ApprovedProcedureStep,
) -> bool:
    """
    Catch-all fail-closed.

    Cualquier mensaje que no coincida con exactamente
    una ruta operativa conocida termina bloqueado.
    """

    return not any(
        (
            route_to_azure_operation(step),
            route_to_database_operation(step),
            route_to_itsm_operation(step),
            route_to_windows_operation(step),
            route_to_linux_operation(step),
            route_to_networking_operation(step),
            route_to_microsoft365_operation(step),
        )
    )