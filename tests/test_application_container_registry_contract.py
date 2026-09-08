from __future__ import annotations

import re
from pathlib import Path


PRODUCT = Path(
    "infra/container-apps/application-registry.bicep"
)


REPOSITORY_READER_ROLE_ID = (
    "b93aa761-3e63-49ed-ac28-beffa264f7ac"
)


def _text():
    assert PRODUCT.is_file()

    return PRODUCT.read_text(
        encoding="utf-8"
    )


def _lowered():
    return _text().casefold()


def _compact():
    return re.sub(
        r"\s+",
        " ",
        _text(),
    )


def test_application_registry_bicep_exists():
    assert PRODUCT.is_file()


def test_registry_module_has_exact_external_parameter_surface():
    text = _text()

    required_parameters = (
        "param registryName string",
        "param location string",
        "param imagePullIdentityName string",
        "param repositoryName string",
    )

    for declaration in required_parameters:
        assert declaration in text

    forbidden_defaults = (
        "param registryName string =",
        "param location string =",
        "param imagePullIdentityName string =",
        "param repositoryName string =",
    )

    for declaration in forbidden_defaults:
        assert declaration not in text


def test_registry_uses_stable_api_basic_sku_and_abac_mode():
    text = _text()

    assert (
        "Microsoft.ContainerRegistry/registries@2025-11-01"
        in text
    )

    compact = _compact()

    assert re.search(
        r"sku:\s*\{\s*name:\s*'Basic'\s*\}",
        compact,
    )

    assert (
        "roleAssignmentMode: 'AbacRepositoryPermissions'"
        in text
    )


def test_registry_security_and_authentication_policy_are_explicit():
    text = _text()

    required = (
        "adminUserEnabled: false",
        "anonymousPullEnabled: false",
        "publicNetworkAccess: 'Enabled'",
        "azureADAuthenticationAsArmPolicy:",
        "status: 'enabled'",
    )

    for fragment in required:
        assert fragment in text

    lowered = text.casefold()

    forbidden = (
        "adminuserenabled: true",
        "anonymouspullenabled: true",
        "username:",
        "password:",
        "credentials:",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_dedicated_image_pull_user_assigned_identity_is_created():
    text = _text()

    assert (
        "Microsoft.ManagedIdentity/"
        "userAssignedIdentities@2023-01-31"
        in text
    )

    assert re.search(
        r"resource\s+imagePullIdentity\s+"
        r"'Microsoft\.ManagedIdentity/"
        r"userAssignedIdentities@2023-01-31'",
        text,
    )

    assert "name: imagePullIdentityName" in text
    assert "location: location" in text


def test_repository_reader_role_assignment_uses_exact_builtin_role():
    text = _text()

    assert (
        "Microsoft.Authorization/"
        "roleAssignments@2022-04-01"
        in text
    )

    assert REPOSITORY_READER_ROLE_ID in text

    assert (
        "Container Registry Repository Reader"
        in text
        or "repositoryReaderRoleDefinitionId"
        in text
    )

    assert "scope: applicationRegistry" in text
    assert (
        "principalId: "
        "imagePullIdentity.properties.principalId"
        in text
    )

    assert "principalType: 'ServicePrincipal'" in text


def test_repository_reader_assignment_is_abac_scoped_to_exact_repository():
    text = _text()

    required = (
        "conditionVersion: '2.0'",
        "repositoryReaderCondition",
        "Microsoft.ContainerRegistry/"
        "registries/repositories/content/read",
        "Microsoft.ContainerRegistry/"
        "registries/repositories/metadata/read",
        "@Request[Microsoft.ContainerRegistry/"
        "registries/repositories:name]",
        "StringEqualsIgnoreCase",
        "repositoryName",
    )

    for fragment in required:
        assert fragment in text


def test_image_pull_identity_has_no_catalog_write_or_legacy_acr_roles():
    lowered = _lowered()

    forbidden = (
        "acrpull",
        "acrpush",
        "container registry repository writer",
        "container registry repository contributor",
        "container registry repository catalog lister",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_image_pull_identity_is_not_reused_from_other_runtime_boundaries():
    lowered = _lowered()

    forbidden_runtime_identity_fragments = (
        "id-app-runtime",
        "id-mcp-read",
        "id-write-vm",
        "id-write-webapp",
        "id-write-aks",
        "teams_managed_identity_client_id",
        "azure_sql_managed_identity_client_id",
        "azure_vm_reader_managed_identity_client_id",
        "foundry_managed_identity_client_id",
    )

    for fragment in forbidden_runtime_identity_fragments:
        assert fragment not in lowered

    assert "systemassigned" not in lowered


def test_registry_module_exposes_only_required_downstream_authority():
    text = _text()

    required_outputs = (
        "output registryId string",
        "output registryLoginServer string",
        "output imagePullIdentityId string",
        "output imagePullIdentityClientId string",
        "output imagePullIdentityPrincipalId string",
        "output repositoryName string",
    )

    for declaration in required_outputs:
        assert declaration in text

    required_values = (
        "applicationRegistry.id",
        "applicationRegistry.properties.loginServer",
        "imagePullIdentity.id",
        "imagePullIdentity.properties.clientId",
        "imagePullIdentity.properties.principalId",
    )

    for fragment in required_values:
        assert fragment in text


def test_registry_module_has_no_container_app_or_image_publication_authority():
    lowered = _lowered()

    forbidden = (
        "microsoft.app/containerapps",
        "microsoft.app/managedenvironments",
        "docker push",
        "az acr login",
        "az acr repository",
        "az acr import",
        "acrtasks",
        "microsoft.containerregistry/registries/tasks",
    )

    for fragment in forbidden:
        assert fragment not in lowered