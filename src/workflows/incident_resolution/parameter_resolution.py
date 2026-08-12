from __future__ import annotations

from src.runtime.procedure.models import (
    ResolvedParameter,
)

from .operational_context import (
    OperationalContext,
    ParameterResolutionResult,
)


#
# ------------------------------------------------------------------
# Allowlist explícita de parámetros soportados
# ------------------------------------------------------------------
#
# Clave:
#   nombre EXACTO que puede solicitar Procedure Execution.
#
# Valor:
#   (
#       atributo de OperationalContext,
#       nombre autoritativo del origen
#   )
#
# No existe normalización de nombres.
# No existe búsqueda fuzzy.
# No existe fallback a raw_attributes.
# No existe inferencia.
#

_PARAMETER_SOURCES: dict[
    str,
    tuple[str, str],
] = {
    "subscription_id": (
        "subscription_id",
        "normalized_alert.subscription_id",
    ),

    "resource_group": (
        "resource_group",
        "normalized_alert.resource_group",
    ),

    "vm_name": (
        "vm_name",
        "normalized_alert.vm_name",
    ),

    "tenant_id": (
        "tenant_id",
        "normalized_alert.tenant_id",
    ),

    "affected_resource": (
        "affected_resource",
        "normalized_alert.affected_resource",
    ),

    "resource_type": (
        "resource_type",
        "normalized_alert.resource_type",
    ),

    "service": (
        "service",
        "normalized_alert.service",
    ),

    "environment": (
        "environment",
        "normalized_alert.environment",
    ),

    "correlation_id": (
        "correlation_id",
        "normalized_alert.correlation_id",
    ),
}


def resolve_required_parameters(
    *,
    required_parameters: list[str],
    context: OperationalContext,
) -> ParameterResolutionResult:
    """
    Resuelve parámetros de procedimiento de forma
    estrictamente determinista.

    Reglas:

    1. Los nombres se conservan literalmente.
    2. No se convierten a lower()/upper().
    3. No se eliminan guiones ni espacios.
    4. No se interpretan pares name=value.
    5. No se consulta raw_attributes.
    6. No se llama a ningún LLM.
    7. No se llama a MCP.
    8. Un parámetro desconocido queda pendiente.
    9. Un parámetro conocido pero sin valor queda pendiente.
    10. Los duplicados se rechazan.
    11. Se conserva el orden original.
    """

    required = list(
        required_parameters
    )

    #
    # Los duplicados crean ambigüedad sobre
    # la identidad operacional aprobada.
    #
    if len(required) != len(set(required)):
        raise ValueError(
            "required_parameters contiene "
            "parámetros duplicados."
        )

    resolved: list[
        ResolvedParameter
    ] = []

    missing: list[str] = []

    for parameter_name in required:
        source_definition = (
            _PARAMETER_SOURCES.get(
                parameter_name
            )
        )

        #
        # Nombre no soportado.
        #
        # Nunca intentamos adivinarlo.
        #
        if source_definition is None:
            missing.append(
                parameter_name
            )
            continue

        (
            attribute_name,
            source_name,
        ) = source_definition

        value = getattr(
            context,
            attribute_name,
        )

        #
        # None o cadena vacía significan:
        # el dato no está disponible.
        #
        if value is None:
            missing.append(
                parameter_name
            )
            continue

        if (
            isinstance(value, str)
            and value == ""
        ):
            missing.append(
                parameter_name
            )
            continue

        resolved.append(
            ResolvedParameter(
                name=parameter_name,
                value=str(value),
                source=source_name,
            )
        )

    return ParameterResolutionResult(
        required_parameters=required,
        resolved_parameters=resolved,
        missing_parameters=missing,
    )