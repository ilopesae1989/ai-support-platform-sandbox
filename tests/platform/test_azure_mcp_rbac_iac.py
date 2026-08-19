from pathlib import Path


INFRA = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra"
)

MAIN = INFRA / "main.bicep"

MODULES = INFRA / "modules"


VM_START_ACTION = (
    "Microsoft.Compute/"
    "virtualMachines/start/action"
)


def _read(path: Path) -> str:
    assert path.exists(), path

    return path.read_text(
        encoding="utf-8"
    )


def test_main_no_longer_requires_storage_resource():
    text = _read(MAIN)

    assert "storageResourceId" not in text
    assert "storageBlobDataReaderRoleId" not in text
    assert (
        "acaStorageBlobRoleAssignment"
        not in text
    )
    assert (
        "acaStorageAccountRoleAssignment"
        not in text
    )


def test_main_declares_exact_target_vm():
    text = _read(MAIN)

    assert "targetVmResourceId" in text


def test_custom_vm_start_role_exists_in_iac():
    matches = []

    for path in MODULES.glob("*.bicep"):
        text = _read(path)

        if VM_START_ACTION in text:
            matches.append(path)

    assert len(matches) == 1, (
        "Debe existir exactamente un módulo "
        "que defina el permiso VM start. "
        f"Encontrados: {matches}"
    )


def test_custom_role_has_only_vm_start_action():
    role_files = []

    for path in MODULES.glob("*.bicep"):
        text = _read(path)

        if VM_START_ACTION in text:
            role_files.append(path)

    assert len(role_files) == 1

    text = _read(role_files[0])

    assert VM_START_ACTION in text

    prohibited = {
        "Microsoft.Compute/virtualMachines/*",
        "Microsoft.Compute/virtualMachines/write",
        "Microsoft.Compute/virtualMachines/delete",
        (
            "Microsoft.Compute/"
            "virtualMachines/powerOff/action"
        ),
        (
            "Microsoft.Compute/"
            "virtualMachines/deallocate/action"
        ),
        (
            "Microsoft.Compute/"
            "virtualMachines/restart/action"
        ),
    }

    for action in prohibited:
        assert action not in text


def test_vm_start_assignment_targets_exact_vm():
    combined = "\n".join(
        _read(path)
        for path in MODULES.glob("*.bicep")
    )

    assert "targetVmResourceId" in combined

    assert (
        "Microsoft.Authorization/"
        "roleAssignments@2022-04-01"
        in combined
    )


def test_subscription_reader_assignment_exists():
    combined = "\n".join(
        _read(path)
        for path in MODULES.glob("*.bicep")
    )

    reader_role_id = (
        "acdd72a7-3385-48ef-bd42-"
        "f606fba81ae7"
    )

    assert reader_role_id in combined

    assert "subscription()" in combined


def test_storage_specific_rbac_modules_are_not_used():
    text = _read(MAIN)

    assert (
        "aca-role-assignment-resource.bicep"
        not in text
    )

    assert (
        "aca-role-assignment-resource-storage.bicep"
        not in text
    )


def test_vm_start_assignment_module_is_resource_group_scoped():
    module_path = (
        MODULES
        / "aca-vm-start-role-assignment.bicep"
    )

    module_text = _read(module_path)
    main_text = _read(MAIN)

    assert (
        "targetScope = 'resourceGroup'"
        in module_text
    )

    assert (
        "scope: resourceGroup("
        in main_text
    )

    assert (
        "scope: subscription()"
        not in _vm_assignment_module_block(
            main_text
        )
    )


def _vm_assignment_module_block(
    main_text: str,
) -> str:
    start_marker = (
        "module acaVmStartRoleAssignment "
    )

    start = main_text.index(
        start_marker
    )

    remainder = main_text[start:]

    next_module = remainder.find(
        "\nmodule ",
        1,
    )

    if next_module == -1:
        return remainder

    return remainder[:next_module]


def test_bicep_config_does_not_enable_experimental_assertions():
    import json

    config_path = INFRA / "bicepconfig.json"

    config = json.loads(
        _read(config_path)
    )

    experimental = config.get(
        "experimentalFeaturesEnabled",
        {}
    )

    assert (
        experimental.get("assertions")
        is not True
    )


def test_infra_contains_no_assert_declarations():
    bicep_files = [
        MAIN,
        *MODULES.glob("*.bicep"),
    ]

    assert_lines = []

    for path in bicep_files:
        for line_number, line in enumerate(
            _read(path).splitlines(),
            start=1,
        ):
            if line.lstrip().startswith("assert "):
                assert_lines.append(
                    (
                        str(path),
                        line_number,
                        line.strip(),
                    )
                )

    assert assert_lines == [], (
        "No se permiten declaraciones Bicep "
        "assert experimentales. "
        f"Encontradas: {assert_lines}"
    )


def test_iac_uses_supported_fail_closed_parameter_validation():
    main_text = _read(MAIN)

    vm_assignment_text = _read(
        MODULES
        / "aca-vm-start-role-assignment.bicep"
    )

    assert "validatedTargetVmResourceId" in main_text
    assert "validatedFoundryProjectResourceId" in main_text

    assert "fail(" in main_text
    assert "fail(" in vm_assignment_text

    assert (
        "targetVmResourceId: validatedTargetVmResourceId"
        in main_text
    )

    assert (
        "foundryProjectResourceId: "
        "validatedFoundryProjectResourceId"
        in main_text
    )
