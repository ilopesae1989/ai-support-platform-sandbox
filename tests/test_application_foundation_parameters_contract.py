from __future__ import annotations

import json
from pathlib import Path


PRODUCT = Path(
    "infra/application-foundation.bicep"
)

PARAMETERS = Path(
    "infra/application-foundation.sandbox.parameters.json"
)

EXPECTED_SCHEMA = (
    "https://schema.management.azure.com/"
    "schemas/2019-04-01/"
    "deploymentParameters.json#"
)

EXPECTED_VALUES = {
    "networkResourceGroupName": "rg-icenter-sandbox-integration",
    "dataResourceGroupName": "rg-icenter-sandbox-data",
    "applicationResourceGroupName": "rg-icenter-sandbox-application",
    "location": "northeurope",
    "sqlLocation": "eastus2",
    "vnetName": "vnet-app-runtime-icenter-sbx-ne",
    "vnetAddressPrefix": "10.240.0.0/24",
    "containerAppsSubnetName": "snet-containerapps-runtime",
    "containerAppsSubnetPrefix": "10.240.0.0/26",
    "privateEndpointSubnetName": "snet-private-endpoints",
    "privateEndpointSubnetPrefix": "10.240.0.64/27",
    "privateDnsZoneName": "privatelink.database.windows.net",
    "sqlServerName": "sql-icenter-app-sbx-eus2-557fda",
    "sqlDatabaseName": "sqldb-ai-support-platform-sbx",
    "sqlRuntimeIdentityName": "id-sql-runtime-icenter-sbx",
    "sqlEntraAdminLogin": (
        "ilopesae_emeal.nttdata.com#EXT#"
        "@NTTDiCenterAILab.onmicrosoft.com"
    ),
    "sqlEntraAdminObjectId": "497a925f-15f1-4583-9d15-29b65590bbcf",
    "tenantId": "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb",
    "databaseSkuName": "Basic",
    "databaseSkuTier": "Basic",
    "databaseSkuCapacity": 5,
    "databaseMaxSizeBytes": 2147483648,
    "privateEndpointName": "pe-sql-app-runtime-icenter-sbx",
    "environmentName": "cae-app-runtime-icenter-sbx",
    "containerAppName": "ca-app-runtime-icenter-sbx",
    "imageByDigest": (
        "acricentersbx4c9f25e9.azurecr.io/"
        "ai-support-platform@"
        "sha256:"
        "02ffeed77179778e64118dc308a3f0b9993e58e288589e6da7dfcecf839e99eb"
    ),
    "registryServer": "acricentersbx4c9f25e9.azurecr.io",
    "imagePullIdentityResourceId": (
        "/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/"
        "resourcegroups/rg-icenter-sandbox-integration/"
        "providers/Microsoft.ManagedIdentity/"
        "userAssignedIdentities/id-acr-pull-icenter-sbx"
    ),
    "teamsIdentityResourceId": (
        "/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/"
        "resourcegroups/rg-icenter-sandbox-integration/"
        "providers/Microsoft.ManagedIdentity/"
        "userAssignedIdentities/id-teams-runtime-icenter-sbx"
    ),
    "azureVmReaderIdentityResourceId": (
        "/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/"
        "resourcegroups/rg-icenter-sandbox-integration/"
        "providers/Microsoft.ManagedIdentity/"
        "userAssignedIdentities/id-vm-reader-icenter-sbx"
    ),
    "foundryIdentityResourceId": (
        "/subscriptions/557fdabc-f3b6-4c24-a9ae-e9e89b5ad172/"
        "resourcegroups/rg-icenter-sandbox-integration/"
        "providers/Microsoft.ManagedIdentity/"
        "userAssignedIdentities/id-foundry-communication-icenter-sbx"
    ),
    "containerCpu": "0.5",
    "containerMemory": "1Gi",
    "clientId": "e89605d4-0a6e-49bb-ae00-4c42a002b6a5",
    "teamsManagedIdentityClientId": "7fa09b7a-cc8f-48e5-af88-1600d924c799",
    "teamsChannelTenantId": "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb",
    "teamsAuthorizedTechniciansGroupObjectId": (
        "2130c010-a41d-4fe5-a9ed-1ef525d26a1a"
    ),
    "foundryProjectEndpoint": (
        "https://aif-icenter-sbx-eus2.services.ai.azure.com/"
        "api/projects/aifproj-icenter-sbx"
    ),
    "foundryManagedIdentityClientId": (
        "4be6b5ed-6c61-447d-8dc5-eded7c03e56c"
    ),
    "azureVmReaderManagedIdentityClientId": (
        "5dfd5c10-53b1-4067-b33c-be7b9fe8a60b"
    ),
}


def test_application_foundation_sandbox_parameter_artifact_contract():
    assert PRODUCT.is_file()
    assert PARAMETERS.is_file()

    payload = json.loads(
        PARAMETERS.read_text(
            encoding="utf-8"
        )
    )

    assert set(payload) == {
        "$schema",
        "contentVersion",
        "parameters",
    }

    assert payload["$schema"] == EXPECTED_SCHEMA
    assert payload["contentVersion"] == "1.0.0.0"

    parameters = payload["parameters"]

    assert isinstance(parameters, dict)
    assert len(parameters) == 40
    assert set(parameters) == set(EXPECTED_VALUES)

    observed = {}

    for name, envelope in parameters.items():
        assert isinstance(envelope, dict)
        assert set(envelope) == {"value"}

        observed[name] = envelope["value"]

    assert observed == EXPECTED_VALUES

    text = PARAMETERS.read_text(
        encoding="utf-8"
    ).casefold()

    forbidden = (
        "teamshitlapproveraadobjectid",
        "teams_hitl_approver_aad_object_id",
        "client_secret",
        "clientsecret",
        "password",
        "connection_string",
        "connectionstring",
        "secretref",
    )

    for fragment in forbidden:
        assert fragment not in text