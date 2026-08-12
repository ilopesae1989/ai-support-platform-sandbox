from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)

from src.runtime.procedure.models import (
    ResolvedParameter,
)

from .alert_models import (
    NormalizedAlert,
)


class OperationalContext(BaseModel):
    """
    Contexto operacional determinista.

    Contiene únicamente valores procedentes
    de campos tipados y confiables del evento
    normalizado.

    No contiene:

    - texto inferido por LLM;
    - valores recuperados de raw_attributes;
    - parámetros inventados;
    - decisiones operativas.
    """

    alert_id: str

    affected_resource: str | None = None
    resource_type: str | None = None

    service: str | None = None
    environment: str | None = None

    subscription_id: str | None = None
    resource_group: str | None = None
    vm_name: str | None = None
    tenant_id: str | None = None

    correlation_id: str | None = None


class ParameterResolutionResult(BaseModel):
    """
    Resultado determinista de resolver
    required_parameters contra OperationalContext.
    """

    required_parameters: list[str] = Field(
        default_factory=list
    )

    resolved_parameters: list[
        ResolvedParameter
    ] = Field(
        default_factory=list
    )

    missing_parameters: list[str] = Field(
        default_factory=list
    )

    @property
    def complete(self) -> bool:
        """
        True únicamente cuando todos los parámetros
        solicitados han podido resolverse.
        """
        return not self.missing_parameters


def build_operational_context(
    alert: NormalizedAlert,
) -> OperationalContext:
    """
    Construye OperationalContext únicamente desde
    campos explícitos de NormalizedAlert.

    IMPORTANTE:

    raw_attributes NO participa en este proceso.

    Esto evita que datos arbitrarios procedentes
    de la fuente de alerta puedan convertirse
    automáticamente en parámetros operativos.
    """

    return OperationalContext(
        alert_id=alert.alert_id,
        affected_resource=(
            alert.affected_resource
        ),
        resource_type=(
            alert.resource_type
        ),
        service=(
            alert.service
        ),
        environment=(
            alert.environment
        ),
        subscription_id=(
            alert.subscription_id
        ),
        resource_group=(
            alert.resource_group
        ),
        vm_name=(
            alert.vm_name
        ),
        tenant_id=(
            alert.tenant_id
        ),
        correlation_id=(
            alert.correlation_id
        ),
    )