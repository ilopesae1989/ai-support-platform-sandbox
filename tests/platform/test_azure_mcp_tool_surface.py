from pathlib import Path


ACA_BICEP_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/modules/"
    "aca-infrastructure.bicep"
)

MAIN_BICEP_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/"
    "main.bicep"
)


EXPECTED_TOOLS = {
    "subscription_list",
    "group_list",
    "group_resource_list",
    "advisor_recommendation_list",
    "advisor_recommendation_summary",
    "compute_vm_power-state",
}


PROHIBITED_TOOLS = {
    "advisor_recommendation_apply",
    "compute_vm_create",
    "compute_vm_delete",
    "compute_vm_update",
    "compute_disk_create",
    "compute_disk_delete",
    "compute_disk_update",
}


def _read(path: Path) -> str:
    assert path.exists()

    return path.read_text(
        encoding="utf-8"
    )


def _executable_text(path: Path) -> str:
    """
    Elimina comentarios Bicep de línea completa.

    Las comprobaciones de seguridad deben validar
    argumentos ejecutables, no documentación textual.
    """
    lines = []

    for line in _read(path).splitlines():
        if line.lstrip().startswith("//"):
            continue

        lines.append(line)

    return "\n".join(lines)


def test_azure_mcp_is_not_global_read_only():
    text = _executable_text(
        ACA_BICEP_PATH
    )

    assert "'--read-only'" not in text


def test_azure_mcp_does_not_use_namespace_surface():
    text = _executable_text(
        ACA_BICEP_PATH
    )

    assert "'--namespace'" not in text
    assert "namespaceArgs" not in text


def test_azure_mcp_module_uses_explicit_tool_filtering():
    text = _executable_text(
        ACA_BICEP_PATH
    )

    assert "param tools array" in text
    assert "'--tool'" in text
    assert "toolArgs" in text


def test_azure_mcp_main_exposes_exact_governed_tools():
    text = _executable_text(
        MAIN_BICEP_PATH
    )

    for tool_name in EXPECTED_TOOLS:
        assert (
            f"'{tool_name}'"
            in text
        ), (
            "Falta tool gobernada: "
            f"{tool_name}"
        )


def test_azure_mcp_main_does_not_expose_prohibited_tools():
    text = _executable_text(
        MAIN_BICEP_PATH
    )

    for tool_name in PROHIBITED_TOOLS:
        assert (
            f"'{tool_name}'"
            not in text
        ), (
            "Tool prohibida publicada: "
            f"{tool_name}"
        )


def test_power_state_is_only_compute_write_surface():
    text = _executable_text(
        MAIN_BICEP_PATH
    )

    assert (
        "'compute_vm_power-state'"
        in text
    )

    prohibited_compute_writes = {
        "compute_vm_create",
        "compute_vm_delete",
        "compute_vm_update",
        "compute_disk_create",
        "compute_disk_delete",
        "compute_disk_update",
        "compute_vmss_create",
        "compute_vmss_delete",
        "compute_vmss_update",
    }

    for tool_name in prohibited_compute_writes:
        assert (
            f"'{tool_name}'"
            not in text
        )
