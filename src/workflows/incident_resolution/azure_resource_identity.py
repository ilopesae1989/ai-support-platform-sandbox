from __future__ import annotations

from .operational_context import (
    OperationalContext,
)

from .resource_identity import (
    ResolvedResourceIdentity,
    ResourceIdentityResolutionError,
)


class AzureResourceIdentityError(
    ValueError
):
    """
    La identidad Azure recibida no puede convertirse
    de forma segura en un Resource ID canónico.
    """

    pass


def _validate_arm_path_segment(
    *,
    name: str,
    value: str,
) -> str:
    """
    Valida un segmento utilizado para construir
    un Resource ID ARM.

    No normaliza.
    No hace strip().
    No cambia mayúsculas/minúsculas.
    No interpreta rutas ARM completas.

    Ante ambigüedad, falla cerrado.
    """

    if not isinstance(
        value,
        str,
    ):
        raise AzureResourceIdentityError(
            f"{name} debe ser un string."
        )

    if not value:
        raise AzureResourceIdentityError(
            f"{name} no puede estar vacío."
        )

    if value != value.strip():
        raise AzureResourceIdentityError(
            f"{name} contiene espacios "
            "al inicio o al final."
        )

    if (
        "/" in value
        or "\\" in value
    ):
        raise AzureResourceIdentityError(
            f"{name} no puede contener "
            "separadores de ruta."
        )

    return value


def build_azure_vm_resource_id(
    *,
    subscription_id: str,
    resource_group: str,
    vm_name: str,
) -> str:
    """
    Construye la identidad ARM canónica de una
    Microsoft.Compute/virtualMachines.

    Autoridad:

        subscription_id
        resource_group
        vm_name

    deben proceder previamente de contexto
    operacional tipado y autoritativo.

    Esta función:

    - no consulta Azure;
    - no consulta MCP;
    - no llama a ningún LLM;
    - no acepta un Resource ID ya construido;
    - no intenta corregir valores;
    - no amplía scope.
    """

    subscription_id = (
        _validate_arm_path_segment(
            name="subscription_id",
            value=subscription_id,
        )
    )

    resource_group = (
        _validate_arm_path_segment(
            name="resource_group",
            value=resource_group,
        )
    )

    vm_name = (
        _validate_arm_path_segment(
            name="vm_name",
            value=vm_name,
        )
    )

    return (
        f"/subscriptions/{subscription_id}"
        f"/resourceGroups/{resource_group}"
        "/providers/Microsoft.Compute"
        f"/virtualMachines/{vm_name}"
    )


class AzureSubscriptionIdentityResolver:
    """
    Resolver autoritativo para operaciones Azure
    cuyo scope operacional es una suscripción.

    Es un adapter de identidad, no lógica de alerta.
    """

    operation_domain = "azure"

    resource_type = "subscription"

    required_parameters = (
        "subscription_id",
    )

    def resolve(
        self,
        context: OperationalContext,
    ) -> ResolvedResourceIdentity:

        if (
            context.resource_type
            != self.resource_type
        ):
            raise (
                ResourceIdentityResolutionError(
                    "resource_type no corresponde "
                    "al resolver de suscripción."
                )
            )

        subscription_id = (
            context.subscription_id
        )

        if (
            subscription_id is None
            or not subscription_id
        ):
            raise (
                ResourceIdentityResolutionError(
                    "La identidad de suscripción "
                    "requiere subscription_id "
                    "autoritativo."
                )
            )

        return ResolvedResourceIdentity(
            operation_domain=(
                self.operation_domain
            ),

            resource_type=(
                self.resource_type
            ),

            canonical_target_resource=(
                "subscription"
            ),

            required_parameters=(
                self.required_parameters
            ),

            allowed_cognitive_targets=(
                "subscription",
                subscription_id,
            ),
        )


class AzureVirtualMachineIdentityResolver:
    """
    Adapter de identidad para:

        Microsoft.Compute/virtualMachines

    No contiene lógica de alertas ni de acciones.

    Sirve igual para cualquier procedimiento/capability
    que opere sobre una VM.
    """

    operation_domain = "azure"

    resource_type = (
        "Microsoft.Compute/"
        "virtualMachines"
    )

    required_parameters = (
        "subscription_id",
        "resource_group",
        "vm_name",
    )

    def resolve(
        self,
        context: OperationalContext,
    ) -> ResolvedResourceIdentity:

        if (
            context.resource_type
            != self.resource_type
        ):
            raise (
                ResourceIdentityResolutionError(
                    "resource_type no corresponde "
                    "al resolver de Azure VM."
                )
            )

        subscription_id = (
            context.subscription_id
        )

        resource_group = (
            context.resource_group
        )

        vm_name = (
            context.vm_name
        )

        if (
            subscription_id is None
            or not subscription_id
        ):
            raise (
                ResourceIdentityResolutionError(
                    "La identidad VM requiere "
                    "subscription_id autoritativo."
                )
            )

        if (
            resource_group is None
            or not resource_group
        ):
            raise (
                ResourceIdentityResolutionError(
                    "La identidad VM requiere "
                    "resource_group autoritativo."
                )
            )

        if (
            vm_name is None
            or not vm_name
        ):
            raise (
                ResourceIdentityResolutionError(
                    "La identidad VM requiere "
                    "vm_name autoritativo."
                )
            )

        if (
            context.affected_resource
            is not None
            and (
                context.affected_resource
                != vm_name
            )
        ):
            raise (
                ResourceIdentityResolutionError(
                    "affected_resource no coincide "
                    "con vm_name autoritativo."
                )
            )

        canonical_resource_id = (
            build_azure_vm_resource_id(
                subscription_id=(
                    subscription_id
                ),

                resource_group=(
                    resource_group
                ),

                vm_name=(
                    vm_name
                ),
            )
        )

        return ResolvedResourceIdentity(
            operation_domain=(
                self.operation_domain
            ),

            resource_type=(
                self.resource_type
            ),

            canonical_target_resource=(
                canonical_resource_id
            ),

            required_parameters=(
                self.required_parameters
            ),

            allowed_cognitive_targets=(
                vm_name,
                canonical_resource_id,
            ),
        )