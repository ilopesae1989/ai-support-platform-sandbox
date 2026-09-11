from __future__ import annotations

import re
from pathlib import Path


PRODUCT = Path(
    "infra/application-foundation.bicep"
)


EXPECTED_PARAMETERS = {
    "networkResourceGroupName": "string",
    "dataResourceGroupName": "string",
    "applicationResourceGroupName": "string",
    "location": "string",
    "sqlLocation": "string",
    "vnetName": "string",
    "vnetAddressPrefix": "string",
    "containerAppsSubnetName": "string",
    "containerAppsSubnetPrefix": "string",
    "privateEndpointSubnetName": "string",
    "privateEndpointSubnetPrefix": "string",
    "privateDnsZoneName": "string",
    "sqlServerName": "string",
    "sqlDatabaseName": "string",
    "sqlRuntimeIdentityName": "string",
    "sqlEntraAdminLogin": "string",
    "sqlEntraAdminObjectId": "string",
    "tenantId": "string",
    "databaseSkuName": "string",
    "databaseSkuTier": "string",
    "databaseSkuCapacity": "int",
    "databaseMaxSizeBytes": "int",
    "privateEndpointName": "string",
    "environmentName": "string",
    "containerAppName": "string",
    "imageByDigest": "string",
    "registryServer": "string",
    "imagePullIdentityResourceId": "string",
    "teamsIdentityResourceId": "string",
    "azureVmReaderIdentityResourceId": "string",
    "foundryIdentityResourceId": "string",
    "containerCpu": "string",
    "containerMemory": "string",
    "clientId": "string",
    "teamsManagedIdentityClientId": "string",
    "teamsChannelTenantId": "string",
    "teamsAuthorizedTechniciansGroupObjectId": "string",
    "foundryProjectEndpoint": "string",
    "foundryManagedIdentityClientId": "string",
    "azureVmReaderManagedIdentityClientId": "string",
}


EXPECTED_MODULE_PATHS = {
    "./network/application-private-network.bicep",
    "./sql/application-sql-foundation.bicep",
    "./network/application-sql-private-link.bicep",
    "./container-apps/application-host.bicep",
}


def _text() -> str:
    assert PRODUCT.is_file(), (
        f"composition root missing: {PRODUCT}"
    )

    return PRODUCT.read_text(
        encoding="utf-8"
    )


def _compact() -> str:
    return re.sub(
        r"\s+",
        " ",
        _text(),
    )


def test_application_foundation_composition_root_exists():
    assert PRODUCT.is_file()


def test_composition_root_is_subscription_scoped():
    text = _text()

    assert re.search(
        r"^targetScope\s*=\s*'subscription'\s*$",
        text,
        flags=re.MULTILINE,
    )


def test_composition_root_has_exact_external_parameter_surface():
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


def test_composition_root_invokes_exactly_four_product_modules():
    text = _text()

    module_paths = set(
        re.findall(
            r"module\s+"
            r"[A-Za-z_][A-Za-z0-9_]*\s+"
            r"'([^']+)'",
            text,
        )
    )

    assert module_paths == EXPECTED_MODULE_PATHS

    declarations = re.findall(
        r"^module\s+"
        r"[A-Za-z_][A-Za-z0-9_]*\s+"
        r"'[^']+'",
        text,
        flags=re.MULTILINE,
    )

    assert len(declarations) == 4


def test_modules_are_scoped_to_exact_resource_group_boundaries():
    compact = _compact()

    required = (
        (
            "module applicationNetwork "
            "'./network/application-private-network.bicep'"
        ),
        "scope: resourceGroup(networkResourceGroupName)",
        (
            "module applicationSql "
            "'./sql/application-sql-foundation.bicep'"
        ),
        "scope: resourceGroup(dataResourceGroupName)",
        (
            "module applicationSqlPrivateLink "
            "'./network/application-sql-private-link.bicep'"
        ),
        (
            "module applicationHost "
            "'./container-apps/application-host.bicep'"
        ),
        "scope: resourceGroup(applicationResourceGroupName)",
    )

    for fragment in required:
        assert fragment in compact

    assert (
        compact.count(
            "scope: resourceGroup(networkResourceGroupName)"
        )
        == 2
    )


def test_network_module_receives_only_external_network_contract():
    text = _text()

    required = (
        "vnetName: vnetName",
        "location: location",
        "vnetAddressPrefix: vnetAddressPrefix",
        "containerAppsSubnetName: containerAppsSubnetName",
        "containerAppsSubnetPrefix: containerAppsSubnetPrefix",
        "privateEndpointSubnetName: privateEndpointSubnetName",
        "privateEndpointSubnetPrefix: privateEndpointSubnetPrefix",
        "privateDnsZoneName: privateDnsZoneName",
    )

    for fragment in required:
        assert fragment in text


def test_sql_module_receives_only_external_sql_bootstrap_contract():
    text = _text()

    required = (
        "sqlServerName: sqlServerName",
        "sqlDatabaseName: sqlDatabaseName",
        "sqlLocation: sqlLocation",
        "sqlRuntimeIdentityName: sqlRuntimeIdentityName",
        "sqlRuntimeIdentityLocation: location",
        "sqlEntraAdminLogin: sqlEntraAdminLogin",
        "sqlEntraAdminObjectId: sqlEntraAdminObjectId",
        "tenantId: tenantId",
        "databaseSkuName: databaseSkuName",
        "databaseSkuTier: databaseSkuTier",
        "databaseSkuCapacity: databaseSkuCapacity",
        "databaseMaxSizeBytes: databaseMaxSizeBytes",
    )

    for fragment in required:
        assert fragment in text


def test_private_link_is_wired_from_network_and_sql_outputs():
    text = _text()

    required = (
        "privateEndpointName: privateEndpointName",
        "location: location",
        (
            "privateEndpointSubnetId: "
            "applicationNetwork.outputs.privateEndpointSubnetId"
        ),
        (
            "sqlServerResourceId: "
            "applicationSql.outputs.sqlServerId"
        ),
        (
            "privateDnsZoneId: "
            "applicationNetwork.outputs.privateDnsZoneId"
        ),
    )

    for fragment in required:
        assert fragment in text


def test_host_consumes_network_and_sql_outputs_directly():
    text = _text()

    required = (
        (
            "infrastructureSubnetId: "
            "applicationNetwork.outputs.containerAppsSubnetId"
        ),
        (
            "azureSqlIdentityResourceId: "
            "applicationSql.outputs.sqlRuntimeIdentityId"
        ),
        (
            "azureSqlServer: "
            "applicationSql.outputs.sqlServerFqdn"
        ),
        (
            "azureSqlDatabase: "
            "applicationSql.outputs.sqlDatabaseName"
        ),
        (
            "azureSqlManagedIdentityClientId: "
            "applicationSql.outputs.sqlRuntimeIdentityClientId"
        ),
    )

    for fragment in required:
        assert fragment in text


def test_host_preserves_existing_certified_external_boundaries():
    text = _text()

    required = (
        "imageByDigest: imageByDigest",
        "registryServer: registryServer",
        (
            "imagePullIdentityResourceId: "
            "imagePullIdentityResourceId"
        ),
        "teamsIdentityResourceId: teamsIdentityResourceId",
        (
            "azureVmReaderIdentityResourceId: "
            "azureVmReaderIdentityResourceId"
        ),
        "foundryIdentityResourceId: foundryIdentityResourceId",
        "clientId: clientId",
        (
            "teamsManagedIdentityClientId: "
            "teamsManagedIdentityClientId"
        ),
        "tenantId: tenantId",
        "teamsChannelTenantId: teamsChannelTenantId",
        (
            "teamsAuthorizedTechniciansGroupObjectId: "
            "teamsAuthorizedTechniciansGroupObjectId"
        ),
        "foundryProjectEndpoint: foundryProjectEndpoint",
        (
            "foundryManagedIdentityClientId: "
            "foundryManagedIdentityClientId"
        ),
        (
            "azureVmReaderManagedIdentityClientId: "
            "azureVmReaderManagedIdentityClientId"
        ),
    )

    for fragment in required:
        assert fragment in text


def test_composition_does_not_reopen_registry_or_existing_identity_creation():
    lowered = _text().casefold()

    forbidden = (
        "application-registry.bicep",
        "microsoft.containerregistry/",
        "microsoft.managedidentity/userassignedidentities",
        "id-acr-pull-icenter-sbx",
        "id-teams-runtime-icenter-sbx",
        "id-foundry-communication-icenter-sbx",
        "id-vm-reader-icenter-sbx",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_composition_has_no_direct_resources_secrets_or_poc_reuse():
    text = _text()
    lowered = text.casefold()

    direct_resources = re.findall(
        r"^resource\s+",
        text,
        flags=re.MULTILINE,
    )

    assert direct_resources == []

    forbidden = (
        "client_secret",
        "clientsecret",
        "password:",
        "administratorloginpassword",
        "systemassigned",
        "sql-icenter-teams-poc-eus2-557fda",
        "azure-mcp-operations-server",
        "poc",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_target_resource_names_and_resource_groups_are_not_hardcoded():
    lowered = _text().casefold()

    forbidden = (
        "rg-icenter-sandbox-integration",
        "rg-icenter-sandbox-data",
        "rg-icenter-sandbox-application",
        "vnet-app-runtime-icenter-sbx-ne",
        "sql-icenter-app-sbx-ne-557fda",
        "sqldb-ai-support-platform-sbx",
        "pe-sql-app-runtime-icenter-sbx",
        "cae-app-runtime-icenter-sbx",
        "ca-app-runtime-icenter-sbx",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_composition_exposes_only_required_deployment_authority():
    text = _text()

    required_outputs = (
        "output vnetId string",
        "output containerAppsSubnetId string",
        "output privateEndpointSubnetId string",
        "output privateDnsZoneId string",
        "output sqlServerId string",
        "output sqlServerFqdn string",
        "output sqlDatabaseName string",
        "output sqlRuntimeIdentityId string",
        "output sqlRuntimeIdentityClientId string",
        "output sqlRuntimeIdentityPrincipalId string",
        "output privateEndpointId string",
        "output environmentId string",
        "output containerAppId string",
        "output containerAppFqdn string",
    )

    for declaration in required_outputs:
        assert declaration in text

    required_values = (
        "applicationNetwork.outputs.vnetId",
        "applicationNetwork.outputs.containerAppsSubnetId",
        "applicationNetwork.outputs.privateEndpointSubnetId",
        "applicationNetwork.outputs.privateDnsZoneId",
        "applicationSql.outputs.sqlServerId",
        "applicationSql.outputs.sqlServerFqdn",
        "applicationSql.outputs.sqlDatabaseName",
        "applicationSql.outputs.sqlRuntimeIdentityId",
        "applicationSql.outputs.sqlRuntimeIdentityClientId",
        "applicationSql.outputs.sqlRuntimeIdentityPrincipalId",
        "applicationSqlPrivateLink.outputs.privateEndpointId",
        "applicationHost.outputs.environmentId",
        "applicationHost.outputs.containerAppId",
        "applicationHost.outputs.containerAppFqdn",
    )

    for fragment in required_values:
        assert fragment in text