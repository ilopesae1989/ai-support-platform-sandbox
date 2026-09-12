from __future__ import annotations

import re
from pathlib import Path


PRODUCT = Path(
    "infra/container-apps/application-host.bicep"
)


EXPECTED_PARAMETERS = {
    "environmentName": "string",
    "containerAppName": "string",
    "location": "string",
    "infrastructureSubnetId": "string",
    "imageByDigest": "string",
    "registryServer": "string",
    "imagePullIdentityResourceId": "string",
    "teamsIdentityResourceId": "string",
    "azureSqlIdentityResourceId": "string",
    "azureVmReaderIdentityResourceId": "string",
    "foundryIdentityResourceId": "string",
    "containerCpu": "string",
    "containerMemory": "string",
    "clientId": "string",
    "teamsManagedIdentityClientId": "string",
    "tenantId": "string",
    "teamsChannelTenantId": "string",
    "teamsAuthorizedTechniciansGroupObjectId": "string",
    "azureSqlServer": "string",
    "azureSqlDatabase": "string",
    "azureSqlManagedIdentityClientId": "string",
    "foundryProjectEndpoint": "string",
    "foundryManagedIdentityClientId": "string",
    "azureVmReaderManagedIdentityClientId": "string",
}


EXPECTED_ENVIRONMENT_VALUES = {
    "CLIENT_ID": "clientId",
    "MANAGED_IDENTITY_CLIENT_ID": (
        "teamsManagedIdentityClientId"
    ),
    "TENANT_ID": "tenantId",
    "TEAMS_CHANNEL_TENANT_ID": (
        "teamsChannelTenantId"
    ),
    "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID": (
        "teamsAuthorizedTechniciansGroupObjectId"
    ),
    "AZURE_SQL_SERVER": "azureSqlServer",
    "AZURE_SQL_DATABASE": "azureSqlDatabase",
    "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID": (
        "azureSqlManagedIdentityClientId"
    ),
    "FOUNDRY_PROJECT_ENDPOINT": (
        "foundryProjectEndpoint"
    ),
    "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
        "foundryManagedIdentityClientId"
    ),
    "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
        "azureVmReaderManagedIdentityClientId"
    ),
}


EXPECTED_RUNTIME_IDENTITIES = (
    "teamsIdentityResourceId",
    "azureSqlIdentityResourceId",
    "azureVmReaderIdentityResourceId",
    "foundryIdentityResourceId",
)


def _text() -> str:
    assert PRODUCT.is_file()

    return PRODUCT.read_text(
        encoding="utf-8"
    )


def _compact() -> str:
    return re.sub(
        r"\s+",
        " ",
        _text(),
    )


def test_application_host_bicep_exists():
    assert PRODUCT.is_file()


def test_host_module_has_exact_external_parameter_surface():
    text = _text()

    declarations = re.findall(
        r"^param\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)\s+"
        r"([A-Za-z_][A-Za-z0-9_]*)"
        r"(\s*=\s*.+)?$",
        text,
        flags=re.MULTILINE,
    )

    observed = {
        name: type_name
        for name, type_name, _default in declarations
    }

    assert observed == EXPECTED_PARAMETERS

    for _name, _type_name, default in declarations:
        assert not default.strip()


def test_host_uses_stable_2026_01_01_container_apps_apis():
    text = _text()

    assert (
        "Microsoft.App/"
        "managedEnvironments@2026-01-01"
        in text
    )

    assert (
        "Microsoft.App/"
        "containerApps@2026-01-01"
        in text
    )

    resource_declarations = re.findall(
        r"resource\s+[A-Za-z_][A-Za-z0-9_]*\s+"
        r"'([^']+)'",
        text,
    )

    assert len(resource_declarations) == 2

    assert set(resource_declarations) == {
        "Microsoft.App/"
        "managedEnvironments@2026-01-01",
        "Microsoft.App/"
        "containerApps@2026-01-01",
    }


def test_host_creates_dedicated_consumption_environment_without_reuse():
    text = _text()
    compact = _compact()

    assert re.search(
        r"resource\s+applicationEnvironment\s+"
        r"'Microsoft\.App/"
        r"managedEnvironments@2026-01-01'",
        text,
    )

    assert "name: environmentName" in text
    assert "location: location" in text

    assert "appLogsConfiguration" not in text
    assert "destination: 'none'" not in text

    assert (
        "publicNetworkAccess: 'Enabled'"
        in text
    )

    lowered = text.casefold()

    assert re.search(
        r"workloadProfiles:\s*\[\s*\{\s*"
        r"name:\s*'Consumption'\s+"
        r"workloadProfileType:\s*'Consumption'\s*"
        r"\}\s*\]",
        compact,
    )
    assert "azure-mcp-operations-server" not in lowered
    assert "cae-app-runtime-icenter-sbx" not in lowered
    assert "ca-app-runtime-icenter-sbx" not in lowered
    assert "poc" not in lowered


def test_container_app_uses_environment_id_and_consumption_profile():
    text = _text()

    assert (
        "environmentId: applicationEnvironment.id"
        in text
    )

    assert (
        "workloadProfileName: 'Consumption'"
        in text
    )

    assert "managedEnvironmentId" not in text


def test_container_app_assigns_only_explicit_user_assigned_boundaries():
    text = _text()

    assert "type: 'UserAssigned'" in text
    assert "SystemAssigned" not in text

    identity_parameters = (
        "imagePullIdentityResourceId",
        *EXPECTED_RUNTIME_IDENTITIES,
    )

    for identity_parameter in identity_parameters:
        assert (
            f"'${{{identity_parameter}}}': {{}}"
            in text
        )

    assert (
        "Microsoft.ManagedIdentity/"
        "userAssignedIdentities"
        not in text
    )


def test_image_pull_identity_is_none_and_runtime_identities_are_main_only():
    text = _text()
    compact = _compact()

    pull_pattern = (
        r"identity:\s*imagePullIdentityResourceId\s+"
        r"lifecycle:\s*'None'"
    )

    assert re.search(
        pull_pattern,
        compact,
    )

    for identity_parameter in EXPECTED_RUNTIME_IDENTITIES:
        pattern = (
            rf"identity:\s*{identity_parameter}\s+"
            r"lifecycle:\s*'Main'"
        )

        assert re.search(
            pattern,
            compact,
        )

    assert (
        compact.count(
            "lifecycle: 'None'"
        )
        == 1
    )

    assert (
        compact.count(
            "lifecycle: 'Main'"
        )
        == 4
    )


def test_registry_auth_uses_pull_identity_without_credentials():
    text = _text()
    compact = _compact()

    assert re.search(
        r"registries:\s*\[\s*\{\s*"
        r"server:\s*registryServer\s+"
        r"identity:\s*imagePullIdentityResourceId\s*"
        r"\}\s*\]",
        compact,
    )

    lowered = text.casefold()

    forbidden = (
        "username:",
        "password:",
        "passwordsecretref:",
        "registrypassword",
        "registryusername",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_image_is_external_digest_authority_and_command_is_not_overridden():
    text = _text()
    lowered = text.casefold()

    assert "image: imageByDigest" in text

    assert "latest" not in lowered
    assert "phase23-23-3d3" not in lowered
    assert (
        "c080161caa1397c3817f66c022ee70e8"
        not in lowered
    )
    assert "acricentersbx4c9f25e9" not in lowered

    assert "command:" not in lowered
    assert "args:" not in lowered


def test_external_ingress_is_https_only_on_port_3978():
    compact = _compact()

    assert re.search(
        r"ingress:\s*\{.*?"
        r"external:\s*true.*?"
        r"targetPort:\s*3978.*?"
        r"allowInsecure:\s*false",
        compact,
    )


def test_single_revision_and_single_replica_are_explicit():
    text = _text()
    compact = _compact()

    assert (
        "activeRevisionsMode: 'Single'"
        in text
    )

    assert re.search(
        r"scale:\s*\{\s*"
        r"minReplicas:\s*1\s+"
        r"maxReplicas:\s*1\s*"
        r"\}",
        compact,
    )


def test_container_resources_are_externalized():
    text = _text()
    compact = _compact()

    assert (
        "cpu: json(containerCpu)"
        in text
    )

    assert (
        "memory: containerMemory"
        in text
    )

    assert re.search(
        r"resources:\s*\{.*?"
        r"cpu:\s*json\(containerCpu\).*?"
        r"memory:\s*containerMemory",
        compact,
    )


def test_runtime_environment_variable_surface_is_exact_and_secret_free():
    text = _text()
    compact = _compact()

    observed_names = set(
        re.findall(
            r"name:\s*'([A-Z][A-Z0-9_]+)'",
            text,
        )
    )

    assert observed_names == set(
        EXPECTED_ENVIRONMENT_VALUES
    )

    for env_name, value_parameter in (
        EXPECTED_ENVIRONMENT_VALUES.items()
    ):
        pattern = (
            rf"name:\s*'{re.escape(env_name)}'\s+"
            rf"value:\s*{re.escape(value_parameter)}"
        )

        assert re.search(
            pattern,
            compact,
        )

    lowered = text.casefold()

    forbidden = (
        "client_secret",
        "secretref:",
        "secrets:",
        "password:",
        "connection_string",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_host_has_no_rbac_registry_identity_or_operational_authority():
    lowered = _text().casefold()

    forbidden = (
        "microsoft.authorization/roleassignments",
        "microsoft.managedidentity/userassignedidentities",
        "microsoft.containerregistry/registries",
        "azure-mcp-operations-server",
        "id-mcp-read",
        "id-write-",
        "docker push",
        "az acr",
        "azure.vm.start",
        "operationresult",
        "approvedprocedurestep",
        "procedureruntimestate",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_host_module_exposes_only_required_downstream_outputs():
    text = _text()

    outputs = set(
        re.findall(
            r"^output\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s+"
            r"[A-Za-z_][A-Za-z0-9_]*",
            text,
            flags=re.MULTILINE,
        )
    )

    assert outputs == {
        "environmentId",
        "containerAppId",
        "containerAppFqdn",
    }

    assert (
        "output environmentId string = "
        "applicationEnvironment.id"
        in text
    )

    assert (
        "output containerAppId string = "
        "applicationHost.id"
        in text
    )

    assert (
        "output containerAppFqdn string = "
        "applicationHost.properties.configuration.ingress.fqdn"
        in text
    )