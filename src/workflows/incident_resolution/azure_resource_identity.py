from __future__ import annotations


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