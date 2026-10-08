from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from src.runtime.procedure.models import (
    OperationAction,
    OperationKind,
)

from .azure_operations_models import VerifiedAzureOperationRequest


class AzureReadToolAuthorityError(ValueError):
    """
    La solicitud READ o la propuesta MCP no coincide
    exactamente con la autoridad Python declarada.
    """

    pass


class AzureReadToolAuthorityRegistryError(ValueError):
    """
    El registro de autoridades READ no puede resolver
    de forma exacta la capability solicitada.
    """

    pass


@dataclass(frozen=True)
class AzureReadToolAuthority:
    """
    Autoridad declarativa para una READ Azure gobernada.

    No ejecuta tools.
    No concede HITL.
    No instala una OperationalCapability.
    No modifica Foundry.
    """

    capability_id: str
    operation_domain: str
    resource_type: str
    operation_action: OperationAction
    target_resource: str
    server_label: str
    tool_name: str
    required_parameters: tuple[str, ...]
    argument_bindings: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        for name in (
            "capability_id",
            "operation_domain",
            "resource_type",
            "target_resource",
            "server_label",
            "tool_name",
        ):
            self._validate_exact_string(
                name=name,
                value=getattr(self, name),
            )

        if self.operation_domain != "azure":
            raise AzureReadToolAuthorityError(
                "operation_domain debe ser exactamente 'azure'."
            )

        if not isinstance(self.operation_action, OperationAction):
            raise AzureReadToolAuthorityError(
                "operation_action debe ser OperationAction."
            )

        if not isinstance(self.required_parameters, tuple):
            raise AzureReadToolAuthorityError(
                "required_parameters debe ser tuple."
            )

        if not self.required_parameters:
            raise AzureReadToolAuthorityError(
                "required_parameters no puede estar vacío."
            )

        if len(self.required_parameters) != len(set(self.required_parameters)):
            raise AzureReadToolAuthorityError(
                "required_parameters contiene duplicados."
            )

        for parameter_name in self.required_parameters:
            self._validate_exact_string(
                name="required_parameter",
                value=parameter_name,
            )

        if not isinstance(self.argument_bindings, tuple):
            raise AzureReadToolAuthorityError(
                "argument_bindings debe ser tuple."
            )

        if not self.argument_bindings:
            raise AzureReadToolAuthorityError(
                "argument_bindings no puede estar vacío."
            )

        argument_names: list[str] = []
        parameter_names: list[str] = []

        for binding in self.argument_bindings:
            if not isinstance(binding, tuple) or len(binding) != 2:
                raise AzureReadToolAuthorityError(
                    "Cada argument_binding debe ser una tuple exacta de dos strings."
                )

            argument_name, parameter_name = binding

            self._validate_exact_string(
                name="tool_argument",
                value=argument_name,
            )
            self._validate_exact_string(
                name="bound_parameter",
                value=parameter_name,
            )

            argument_names.append(argument_name)
            parameter_names.append(parameter_name)

        if len(argument_names) != len(set(argument_names)):
            raise AzureReadToolAuthorityError(
                "argument_bindings contiene argumentos MCP duplicados."
            )

        if tuple(parameter_names) != self.required_parameters:
            raise AzureReadToolAuthorityError(
                "argument_bindings debe cubrir exactamente required_parameters en el mismo orden."
            )

    @staticmethod
    def _validate_exact_string(*, name: str, value) -> None:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
        ):
            raise AzureReadToolAuthorityError(
                f"{name} debe ser un string exacto no vacío."
            )

    def validate_pending_approval(
        self,
        *,
        request: VerifiedAzureOperationRequest,
        approval,
    ) -> None:
        if not isinstance(request, VerifiedAzureOperationRequest):
            raise AzureReadToolAuthorityError(
                "request debe ser VerifiedAzureOperationRequest."
            )

        if request.security_verified is not True:
            raise AzureReadToolAuthorityError(
                "La READ gobernada requiere security_verified=True."
            )

        if request.verification_source != "pre_call_security_verifier":
            raise AzureReadToolAuthorityError(
                "verification_source no es el PreCall autoritativo."
            )

        if request.operation_domain != self.operation_domain:
            raise AzureReadToolAuthorityError(
                "operation_domain no coincide con la autoridad READ."
            )

        if request.operation_kind != OperationKind.READ:
            raise AzureReadToolAuthorityError(
                "La autoridad sólo permite READ."
            )

        if request.operation_action != self.operation_action:
            raise AzureReadToolAuthorityError(
                "operation_action no coincide con la autoridad READ."
            )

        if request.capability_id != self.capability_id:
            raise AzureReadToolAuthorityError(
                "capability_id no coincide con la autoridad READ."
            )

        if request.target_resource != self.target_resource:
            raise AzureReadToolAuthorityError(
                "target_resource no coincide con la autoridad READ."
            )

        if tuple(request.required_parameters) != self.required_parameters:
            raise AzureReadToolAuthorityError(
                "required_parameters no coincide exactamente con la autoridad READ."
            )

        resolved_names = tuple(
            parameter.name
            for parameter in request.resolved_parameters
        )

        if resolved_names != self.required_parameters:
            raise AzureReadToolAuthorityError(
                "resolved_parameters no coincide exactamente con required_parameters."
            )

        if len(resolved_names) != len(set(resolved_names)):
            raise AzureReadToolAuthorityError(
                "resolved_parameters contiene duplicados."
            )

        resolved: dict[str, str] = {}

        for parameter in request.resolved_parameters:
            self._validate_exact_string(
                name="resolved_parameter.name",
                value=parameter.name,
            )
            self._validate_exact_string(
                name="resolved_parameter.value",
                value=parameter.value,
            )
            resolved[parameter.name] = parameter.value

        expected_arguments = {
            argument_name: resolved[parameter_name]
            for argument_name, parameter_name
            in self.argument_bindings
        }

        server_label = getattr(approval, "server_label", None)
        tool_name = getattr(approval, "tool_name", None)
        arguments = getattr(approval, "arguments", None)

        if server_label != self.server_label:
            raise AzureReadToolAuthorityError(
                "server_label MCP no coincide con la autoridad READ."
            )

        if tool_name != self.tool_name:
            raise AzureReadToolAuthorityError(
                "tool MCP no coincide con la autoridad READ."
            )

        if not isinstance(arguments, dict):
            raise AzureReadToolAuthorityError(
                "arguments MCP debe ser un dict."
            )

        if arguments != expected_arguments:
            raise AzureReadToolAuthorityError(
                "arguments MCP no coincide exactamente con los parámetros autorizados."
            )


class AzureReadToolAuthorityRegistry:
    """
    Registro exacto de autoridades READ Azure.
    """

    def __init__(
        self,
        *,
        authorities: Iterable[AzureReadToolAuthority],
    ) -> None:
        self._authorities: dict[
            str,
            AzureReadToolAuthority,
        ] = {}

        for authority in authorities:
            if not isinstance(authority, AzureReadToolAuthority):
                raise AzureReadToolAuthorityRegistryError(
                    "Sólo pueden registrarse AzureReadToolAuthority."
                )

            if authority.capability_id in self._authorities:
                raise AzureReadToolAuthorityRegistryError(
                    "capability_id READ duplicado: "
                    f"{authority.capability_id!r}."
                )

            self._authorities[authority.capability_id] = authority

    def get(
        self,
        capability_id: str,
    ) -> AzureReadToolAuthority:
        authority = self._authorities.get(capability_id)

        if authority is None:
            raise AzureReadToolAuthorityRegistryError(
                "No existe autoridad READ para "
                f"capability_id={capability_id!r}."
            )

        return authority

    def count(self) -> int:
        return len(self._authorities)


def build_default_azure_read_tool_authority_registry(
) -> AzureReadToolAuthorityRegistry:
    return AzureReadToolAuthorityRegistry(
        authorities=(
            AzureReadToolAuthority(
                capability_id="azure.resource_group.list",
                operation_domain="azure",
                resource_type="subscription",
                operation_action=OperationAction.RESOURCE_GROUP_LIST,
                target_resource="subscription",
                server_label="azure-mcp-operations-sbx",
                tool_name="group_list",
                required_parameters=(
                    "subscription_id",
                ),
                argument_bindings=(
                    (
                        "subscription",
                        "subscription_id",
                    ),
                ),
            ),
        )
    )
