from __future__ import annotations

import re
from pathlib import Path


HOST = Path(
    "infra/container-apps/application-host.bicep"
)

NETWORK = Path(
    "infra/network/application-private-network.bicep"
)

SQL = Path(
    "infra/sql/application-sql-foundation.bicep"
)

PRIVATE_LINK = Path(
    "infra/network/application-sql-private-link.bicep"
)


def _text(path: Path) -> str:
    assert path.is_file(), (
        f"required IaC file missing: {path}"
    )

    return path.read_text(
        encoding="utf-8"
    )


def _compact(path: Path) -> str:
    return re.sub(
        r"\s+",
        " ",
        _text(path),
    )


def _assert_external_parameters(
    *,
    path: Path,
    declarations: tuple[str, ...],
) -> None:
    text = _text(path)

    for declaration in declarations:
        assert declaration in text
        assert f"{declaration} =" not in text


# ================================================================
# EXISTING HOST E3 NETWORK EXTENSION
# ================================================================


def test_host_requires_external_infrastructure_subnet_id():
    _assert_external_parameters(
        path=HOST,
        declarations=(
            "param infrastructureSubnetId string",
        ),
    )


def test_host_managed_environment_uses_external_custom_vnet():
    text = _text(HOST)
    compact = _compact(HOST)

    assert "vnetConfiguration:" in text

    assert (
        "infrastructureSubnetId: infrastructureSubnetId"
        in text
    )

    assert re.search(
        r"vnetConfiguration:\s*\{"
        r".*?"
        r"internal:\s*false"
        r".*?"
        r"\}",
        compact,
    )


def test_host_explicitly_pins_consumption_workload_profile():
    text = _text(HOST)

    assert "workloadProfiles:" in text

    assert re.search(
        r"name:\s*'Consumption'",
        text,
    )

    assert re.search(
        r"workloadProfileType:\s*'Consumption'",
        text,
    )

    assert (
        "workloadProfileName: 'Consumption'"
        in text
    )


# ================================================================
# PRIVATE NETWORK FOUNDATION
# ================================================================


def test_private_network_module_exists():
    assert NETWORK.is_file()


def test_private_network_has_exact_external_parameter_surface():
    _assert_external_parameters(
        path=NETWORK,
        declarations=(
            "param vnetName string",
            "param location string",
            "param vnetAddressPrefix string",
            "param containerAppsSubnetName string",
            "param containerAppsSubnetPrefix string",
            "param privateEndpointSubnetName string",
            "param privateEndpointSubnetPrefix string",
            "param privateDnsZoneName string",
        ),
    )


def test_private_network_uses_current_stable_resource_apis():
    text = _text(NETWORK)

    required = (
        "Microsoft.Network/virtualNetworks@2025-05-01",
        "Microsoft.Network/virtualNetworks/subnets@2025-05-01",
        "Microsoft.Network/privateDnsZones@2024-06-01",
        "Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01",
    )

    for fragment in required:
        assert fragment in text

    assert "preview" not in text.casefold()


def test_private_network_creates_vnet_and_both_dedicated_subnets():
    text = _text(NETWORK)

    required = (
        "name: vnetName",
        "addressPrefixes:",
        "vnetAddressPrefix",
        "name: containerAppsSubnetName",
        "addressPrefix: containerAppsSubnetPrefix",
        "name: privateEndpointSubnetName",
        "addressPrefix: privateEndpointSubnetPrefix",
    )

    for fragment in required:
        assert fragment in text


def test_container_apps_subnet_is_dedicated_and_delegated():
    text = _text(NETWORK)

    assert (
        "Microsoft.App/environments"
        in text
    )

    assert re.search(
        r"delegations:\s*\["
        r".*?"
        r"serviceName:\s*'Microsoft\.App/environments'"
        r".*?"
        r"\]",
        _compact(NETWORK),
    )


def test_network_creates_sql_private_dns_zone_and_vnet_link():
    text = _text(NETWORK)

    required = (
        "name: privateDnsZoneName",
        "location: 'global'",
        "registrationEnabled: false",
        "virtualNetwork:",
        "id: applicationVnet.id",
    )

    for fragment in required:
        assert fragment in text


def test_network_outputs_only_required_downstream_resource_ids():
    text = _text(NETWORK)

    required = (
        "output vnetId string",
        "output containerAppsSubnetId string",
        "output privateEndpointSubnetId string",
        "output privateDnsZoneId string",
    )

    for declaration in required:
        assert declaration in text

    required_values = (
        "applicationVnet.id",
        "containerAppsSubnet.id",
        "privateEndpointSubnet.id",
        "sqlPrivateDnsZone.id",
    )

    for fragment in required_values:
        assert fragment in text


# ================================================================
# PRODUCTIVE AZURE SQL FOUNDATION
# ================================================================


def test_productive_sql_foundation_module_exists():
    assert SQL.is_file()


def test_productive_sql_has_exact_external_parameter_surface():
    _assert_external_parameters(
        path=SQL,
        declarations=(
            "param sqlServerName string",
            "param sqlDatabaseName string",
            "param sqlLocation string",
            "param sqlRuntimeIdentityName string",
            "param sqlRuntimeIdentityLocation string",
            "param sqlEntraAdminLogin string",
            "param sqlEntraAdminObjectId string",
            "param tenantId string",
            "param databaseSkuName string",
            "param databaseSkuTier string",
            "param databaseSkuCapacity int",
            "param databaseMaxSizeBytes int",
        ),
    )


def test_productive_sql_creates_dedicated_runtime_uami():
    text = _text(SQL)

    assert (
        "Microsoft.ManagedIdentity/"
        "userAssignedIdentities@2023-01-31"
        in text
    )

    assert re.search(
        r"resource\s+sqlRuntimeIdentity\s+"
        r"'Microsoft\.ManagedIdentity/"
        r"userAssignedIdentities@2023-01-31'",
        text,
    )

    assert "name: sqlRuntimeIdentityName" in text
    assert "location: sqlRuntimeIdentityLocation" in text


def test_productive_sql_is_entra_only_without_sql_credentials():
    text = _text(SQL)
    lowered = text.casefold()

    assert (
        "Microsoft.Sql/servers@2025-01-01"
        in text
    )

    required = (
        "administrators:",
        "administratorType: 'ActiveDirectory'",
        "azureADOnlyAuthentication: true",
        "login: sqlEntraAdminLogin",
        "principalType: 'User'",
        "sid: sqlEntraAdminObjectId",
        "tenantId: tenantId",
    )

    for fragment in required:
        assert fragment in text

    forbidden = (
        "administratorloginpassword",
        "administratorlogin:",
        "password:",
        "pwd=",
        "client_secret",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_productive_sql_server_security_is_explicit():
    text = _text(SQL)

    required = (
        "minimalTlsVersion: '1.2'",
        "publicNetworkAccess: 'Disabled'",
        "version: '12.0'",
    )

    for fragment in required:
        assert fragment in text

    assert "publicNetworkAccess: 'Enabled'" not in text


def test_productive_sql_database_uses_parameterized_sku():
    text = _text(SQL)

    assert (
        "Microsoft.Sql/servers/databases@2025-01-01"
        in text
    )

    required = (
        "name: sqlDatabaseName",
        "name: databaseSkuName",
        "tier: databaseSkuTier",
        "capacity: databaseSkuCapacity",
        "maxSizeBytes: databaseMaxSizeBytes",
    )

    for fragment in required:
        assert fragment in text


def test_productive_sql_exposes_runtime_and_database_authority():
    text = _text(SQL)
    lowered = text.casefold()

    required = (
        "output sqlServerId string",
        "output sqlServerFqdn string",
        "output sqlDatabaseName string",
        "output sqlRuntimeIdentityId string",
        "output sqlRuntimeIdentityClientId string",
        "output sqlRuntimeIdentityPrincipalId string",
    )

    for declaration in required:
        assert declaration in text

    forbidden = (
        "sql-icenter-teams-poc-eus2-557fda",
        "allowazureservices",
        "0.0.0.0",
        "db_owner",
        "directory readers",
        "application.read.all",
    )

    for fragment in forbidden:
        assert fragment not in lowered


# ================================================================
# SQL PRIVATE LINK
# ================================================================


def test_sql_private_link_module_exists():
    assert PRIVATE_LINK.is_file()


def test_sql_private_link_uses_exact_private_endpoint_contract():
    text = _text(PRIVATE_LINK)

    _assert_external_parameters(
        path=PRIVATE_LINK,
        declarations=(
            "param privateEndpointName string",
            "param location string",
            "param privateEndpointSubnetId string",
            "param sqlServerResourceId string",
            "param privateDnsZoneId string",
        ),
    )

    assert (
        "Microsoft.Network/privateEndpoints@2025-05-01"
        in text
    )

    required = (
        "id: privateEndpointSubnetId",
        "privateLinkServiceId: sqlServerResourceId",
        "groupIds:",
        "'sqlServer'",
    )

    for fragment in required:
        assert fragment in text


def test_sql_private_link_binds_private_dns_zone_group():
    text = _text(PRIVATE_LINK)

    assert (
        "Microsoft.Network/"
        "privateEndpoints/privateDnsZoneGroups@2025-05-01"
        in text
    )

    required = (
        "privateDnsZoneConfigs:",
        "privateDnsZoneId: privateDnsZoneId",
        "output privateEndpointId string",
    )

    for fragment in required:
        assert fragment in text

def test_productive_sql_decouples_runtime_identity_from_sql_region():
    text = _text(SQL)

    assert "param location string" not in text
    assert "param sqlLocation string" in text
    assert "param sqlRuntimeIdentityLocation string" in text

    assert text.count(
        "location: sqlRuntimeIdentityLocation"
    ) == 1

    assert text.count(
        "location: sqlLocation"
    ) == 2
