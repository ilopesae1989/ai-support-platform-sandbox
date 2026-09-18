from __future__ import annotations

import importlib
import inspect
import json

from dataclasses import fields

import pytest


SOURCE_TENANT_ID = (
    "3048dc87-43f0-4100-9acb-ae1971c79395"
)

SOURCE_USER_OBJECT_ID = (
    "69916319-588a-42a9-9109-b57c6d1c7501"
)

AUTHORIZATION_TENANT_ID = (
    "0cb40b2b-6cfc-4c63-bf7b-da710ea390cb"
)

AUTHORIZATION_USER_OBJECT_ID = (
    "497a925f-15f1-4583-9d15-29b65590bbcf"
)

AUTHORIZED_GROUP_OBJECT_ID = (
    "2130c010-a41d-4fe5-a9ed-1ef525d26a1a"
)

TEAMS_IDENTITY_CLIENT_ID = (
    "7fa09b7a-cc8f-48e5-af88-1600d924c799"
)


def _resolver_module():
    return importlib.import_module(
        "src.channels.teams.authorization_identity_resolver"
    )


def _production_settings_module():
    return importlib.import_module(
        "src.channels.teams.production_settings"
    )


def _bootstrap_module():
    return importlib.import_module(
        "src.channels.teams.bootstrap"
    )


def _handler_module():
    return importlib.import_module(
        "src.channels.teams.incident_approval_handoff_handler"
    )


def _production_bootstrap_module():
    return importlib.import_module(
        "src.channels.teams.production_bootstrap"
    )


def _production_composition_module():
    return importlib.import_module(
        "src.channels.teams.production_composition"
    )


def _mapping_payload():
    return [
        {
            "sourceTenantId": SOURCE_TENANT_ID,
            "sourceUserObjectId": SOURCE_USER_OBJECT_ID,
            "targetTenantId": AUTHORIZATION_TENANT_ID,
            "targetUserObjectId": AUTHORIZATION_USER_OBJECT_ID,
        }
    ]


def _environment():
    return {
        "CLIENT_ID": (
            "e89605d4-0a6e-49bb-ae00-4c42a002b6a5"
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            TEAMS_IDENTITY_CLIENT_ID
        ),
        "TENANT_ID": (
            AUTHORIZATION_TENANT_ID
        ),
        "TEAMS_CHANNEL_TENANT_ID": (
            SOURCE_TENANT_ID
        ),
        "TEAMS_AUTHORIZATION_DIRECTORY_TENANT_ID": (
            AUTHORIZATION_TENANT_ID
        ),
        "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON": (
            json.dumps(
                _mapping_payload(),
                separators=(",", ":"),
            )
        ),
        "TEAMS_AUTHORIZED_TECHNICIANS_GROUP_OBJECT_ID": (
            AUTHORIZED_GROUP_OBJECT_ID
        ),
        "AZURE_SQL_SERVER": (
            "sql.example.database.windows.net"
        ),
        "AZURE_SQL_DATABASE": (
            "ai-support-platform"
        ),
    }


@pytest.mark.asyncio
async def test_exact_production_resolver_maps_only_explicit_directory_tuple():
    module = _resolver_module()

    mapping_type = getattr(
        module,
        "ExactTeamsAuthorizationIdentityMapping",
    )

    resolver_type = getattr(
        module,
        "ExactTeamsAuthorizationObjectIdResolver",
    )

    error_type = getattr(
        module,
        "AuthorizationIdentityResolutionError",
    )

    mapping = mapping_type(
        source_tenant_id=SOURCE_TENANT_ID,
        source_user_object_id=SOURCE_USER_OBJECT_ID,
        target_tenant_id=AUTHORIZATION_TENANT_ID,
        target_user_object_id=(
            AUTHORIZATION_USER_OBJECT_ID
        ),
    )

    resolver = resolver_type(
        mappings=(
            mapping,
        )
    )

    resolved = await (
        resolver.resolve_authorization_user_object_id(
            source_tenant_id=SOURCE_TENANT_ID,
            source_user_object_id=SOURCE_USER_OBJECT_ID,
            target_tenant_id=AUTHORIZATION_TENANT_ID,
        )
    )

    assert (
        resolved
        == AUTHORIZATION_USER_OBJECT_ID
    )

    with pytest.raises(
        error_type
    ):
        await resolver.resolve_authorization_user_object_id(
            source_tenant_id=SOURCE_TENANT_ID,
            source_user_object_id=(
                "11111111-1111-4111-8111-111111111111"
            ),
            target_tenant_id=AUTHORIZATION_TENANT_ID,
        )


def test_exact_mapping_surface_forbids_identity_inference_attributes():
    module = _resolver_module()

    mapping_type = getattr(
        module,
        "ExactTeamsAuthorizationIdentityMapping",
    )

    assert tuple(
        field.name
        for field in fields(
            mapping_type
        )
    ) == (
        "source_tenant_id",
        "source_user_object_id",
        "target_tenant_id",
        "target_user_object_id",
    )

    forbidden = {
        "mail",
        "email",
        "upn",
        "user_principal_name",
        "display_name",
        "name",
    }

    assert forbidden.isdisjoint(
        {
            field.name
            for field in fields(
                mapping_type
            )
        }
    )


def test_cross_tenant_production_settings_parse_exact_authorization_authority():
    module = _production_settings_module()

    settings = (
        module
        .build_production_teams_host_settings(
            _environment()
        )
    )

    assert tuple(
        field.name
        for field in fields(
            type(settings)
        )
    ) == (
        "app_settings",
        "azure_sql_settings",
        "authorization_identity_mappings",
    )

    assert (
        settings
        .app_settings
        .teams_channel_tenant_id
        == SOURCE_TENANT_ID
    )

    assert (
        settings
        .app_settings
        .authorization_directory_tenant_id
        == AUTHORIZATION_TENANT_ID
    )

    assert (
        settings
        .app_settings
        .authorized_technicians_group_object_id
        == AUTHORIZED_GROUP_OBJECT_ID
    )

    assert len(
        settings.authorization_identity_mappings
    ) == 1

    mapping = (
        settings
        .authorization_identity_mappings[0]
    )

    assert (
        mapping.source_tenant_id
        == SOURCE_TENANT_ID
    )

    assert (
        mapping.source_user_object_id
        == SOURCE_USER_OBJECT_ID
    )

    assert (
        mapping.target_tenant_id
        == AUTHORIZATION_TENANT_ID
    )

    assert (
        mapping.target_user_object_id
        == AUTHORIZATION_USER_OBJECT_ID
    )


def test_cross_tenant_production_settings_fail_closed_without_mapping():
    module = _production_settings_module()

    environment = _environment()

    environment.pop(
        "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
    )

    with pytest.raises(
        module.TeamsProductionHostConfigurationError,
        match=(
            "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
        ),
    ):
        module.build_production_teams_host_settings(
            environment
        )


def test_cross_tenant_production_settings_reject_identity_inference_payload():
    module = _production_settings_module()

    environment = _environment()

    environment[
        "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
    ] = json.dumps(
        [
            {
                "sourceTenantId": SOURCE_TENANT_ID,
                "sourceUserObjectId": SOURCE_USER_OBJECT_ID,
                "targetTenantId": AUTHORIZATION_TENANT_ID,
                "targetUserObjectId": (
                    AUTHORIZATION_USER_OBJECT_ID
                ),
                "mail": "forbidden@example.com",
            }
        ],
        separators=(",", ":"),
    )

    with pytest.raises(
        module.TeamsProductionHostConfigurationError
    ):
        module.build_production_teams_host_settings(
            environment
        )


def test_bootstrap_and_handler_have_explicit_resolver_boundary():
    bootstrap = _bootstrap_module()
    handler = _handler_module()

    bootstrap_signature = inspect.signature(
        bootstrap.build_teams_hitl_app
    )

    assert (
        "operator_identity_resolver"
        in bootstrap_signature.parameters
    )

    dependency_fields = tuple(
        field.name
        for field in fields(
            handler.TeamsApprovalHandlerDependencies
        )
    )

    assert (
        "operator_identity_resolver"
        in dependency_fields
    )

    handler_source = inspect.getsource(
        handler.handle_teams_approval_action
    )

    assert (
        "operator_identity_resolver="
        in handler_source
    )


def test_production_bootstrap_propagates_explicit_resolver():
    module = _production_bootstrap_module()

    signature = inspect.signature(
        module.build_production_teams_hitl_app
    )

    assert (
        "operator_identity_resolver"
        in signature.parameters
    )

    source = inspect.getsource(
        module.build_production_teams_hitl_app
    )

    assert (
        "operator_identity_resolver="
        in source
    )


def test_production_composition_builds_exact_resolver_from_typed_mappings():
    module = _production_composition_module()

    source = inspect.getsource(
        module.build_production_teams_host
    )

    assert (
        "build_exact_teams_authorization_object_id_resolver"
        in source
    )

    assert (
        "authorization_identity_mappings"
        in source
    )

    assert (
        "operator_identity_resolver="
        in source
    )


def test_production_authorization_contract_contains_no_inference_keys():
    modules = (
        _resolver_module(),
        _production_settings_module(),
        _production_composition_module(),
    )

    source = "\n".join(
        inspect.getsource(
            module
        )
        for module in modules
    ).lower()

    forbidden_fragments = (
        "display_name",
        "displayname",
        "userprincipalname",
        "user_principal_name",
        "mail eq",
        "startswith(mail",
        "startswith(userprincipalname",
    )

    for fragment in forbidden_fragments:
        assert fragment not in source