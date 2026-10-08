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


def _is_post_hitl_execution_eligible(
    step: ApprovedProcedureStep,
) -> bool:
    if step.approved is not True:
        return False

    if (
        step.next_action
        != NextAction.EXECUTE_STEP
    ):
        return False

    if (
        step.operation_kind
        not in ROUTABLE_OPERATION_KINDS
    ):
        return False

    return True


def is_post_hitl_routable(
    step: ApprovedProcedureStep,
) -> bool:
    """
    Gate común de seguridad post-HITL para rutas legacy conocidas.

    Ningún LLM participa aquí.
    """

    return (
        _is_post_hitl_execution_eligible(step)
        and step.operation_domain
        in SUPPORTED_OPERATION_DOMAINS
    )


def build_registered_operation_route(
    operation_domain: str,
):
    """
    Crea un predicado exacto para un dominio ya registrado.

    Registrar el dominio no concede capability, aprobación ni autoridad.
    El predicado sólo conserva las gates deterministas post-HITL comunes.
    """

    if (
        not isinstance(operation_domain, str)
        or not operation_domain
        or operation_domain != operation_domain.strip()
    ):
        raise ValueError(
            "operation_domain debe ser string exacto no vacío."
        )

    def route(
        step: ApprovedProcedureStep,
    ) -> bool:
        return (
            _is_post_hitl_execution_eligible(step)
            and step.operation_domain
            == operation_domain
        )

    return route


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