from __future__ import annotations

import importlib
import inspect
import textwrap
from dataclasses import fields

import pytest


TARGET_MODULE = (
    "src.agents.production_settings"
)

PROJECT_ENDPOINT = (
    "https://aif-example.services.ai.azure.com/"
    "api/projects/project-example"
)

USER_ASSIGNED_CLIENT_ID = (
    "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
)


def _module():
    return importlib.import_module(
        TARGET_MODULE
    )


def test_foundry_production_settings_has_exact_surface():
    module = _module()

    settings_type = getattr(
        module,
        "FoundryProductionSettings",
        None,
    )

    builder = getattr(
        module,
        "build_foundry_production_settings",
        None,
    )

    assert settings_type is not None
    assert callable(builder)

    assert tuple(
        field.name
        for field in fields(
            settings_type
        )
    ) == (
        "project_endpoint",
        "managed_identity_client_id",
    )

    signature = inspect.signature(
        builder
    )

    assert tuple(
        signature.parameters
    ) == (
        "environment",
    )


def test_foundry_project_endpoint_is_required_and_preserved_exactly():
    module = _module()

    settings = (
        module
        .build_foundry_production_settings(
            {
                "FOUNDRY_PROJECT_ENDPOINT": (
                    PROJECT_ENDPOINT
                ),
            }
        )
    )

    assert (
        settings.project_endpoint
        == PROJECT_ENDPOINT
    )

    assert (
        settings.managed_identity_client_id
        is None
    )

    for invalid_environment in (
        {},
        {
            "FOUNDRY_PROJECT_ENDPOINT": "",
        },
        {
            "FOUNDRY_PROJECT_ENDPOINT": " ",
        },
        {
            "FOUNDRY_PROJECT_ENDPOINT": (
                " " + PROJECT_ENDPOINT
            ),
        },
        {
            "FOUNDRY_PROJECT_ENDPOINT": (
                PROJECT_ENDPOINT + " "
            ),
        },
    ):
        with pytest.raises(
            ValueError
        ):
            module.build_foundry_production_settings(
                invalid_environment
            )


def test_absent_foundry_client_id_means_system_assigned_identity():
    module = _module()

    settings = (
        module
        .build_foundry_production_settings(
            {
                "FOUNDRY_PROJECT_ENDPOINT": (
                    PROJECT_ENDPOINT
                ),
            }
        )
    )

    assert (
        settings.managed_identity_client_id
        is None
    )


def test_user_assigned_foundry_client_id_is_exact_and_canonical():
    module = _module()

    settings = (
        module
        .build_foundry_production_settings(
            {
                "FOUNDRY_PROJECT_ENDPOINT": (
                    PROJECT_ENDPOINT
                ),
                "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
                    USER_ASSIGNED_CLIENT_ID
                ),
            }
        )
    )

    assert (
        settings.managed_identity_client_id
        == USER_ASSIGNED_CLIENT_ID
    )

    for invalid_client_id in (
        "",
        " ",
        "system",
        "not-a-guid",
        USER_ASSIGNED_CLIENT_ID.upper(),
        " " + USER_ASSIGNED_CLIENT_ID,
        USER_ASSIGNED_CLIENT_ID + " ",
    ):
        with pytest.raises(
            ValueError
        ):
            module.build_foundry_production_settings(
                {
                    "FOUNDRY_PROJECT_ENDPOINT": (
                        PROJECT_ENDPOINT
                    ),
                    "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
                        invalid_client_id
                    ),
                }
            )


def test_foundry_identity_settings_are_independent_from_other_identity_names():
    module = _module()

    baseline = (
        module
        .build_foundry_production_settings(
            {
                "FOUNDRY_PROJECT_ENDPOINT": (
                    PROJECT_ENDPOINT
                ),
            }
        )
    )

    environment = {
        "FOUNDRY_PROJECT_ENDPOINT": (
            PROJECT_ENDPOINT
        ),
        "MANAGED_IDENTITY_CLIENT_ID": (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        ),
        "AZURE_SQL_MANAGED_IDENTITY_CLIENT_ID": (
            "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        ),
        "AZURE_VM_READER_MANAGED_IDENTITY_CLIENT_ID": (
            "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        ),
    }

    with_other_identities = (
        module
        .build_foundry_production_settings(
            environment
        )
    )

    assert (
        with_other_identities
        == baseline
    )

    assert (
        with_other_identities
        .managed_identity_client_id
        is None
    )


def test_environment_mapping_is_not_mutated():
    module = _module()

    environment = {
        "FOUNDRY_PROJECT_ENDPOINT": (
            PROJECT_ENDPOINT
        ),
        "FOUNDRY_MANAGED_IDENTITY_CLIENT_ID": (
            USER_ASSIGNED_CLIENT_ID
        ),
    }

    before = dict(
        environment
    )

    module.build_foundry_production_settings(
        environment
    )

    assert environment == before


def test_settings_boundary_has_no_credential_runtime_or_channel_authority():
    module = _module()

    source = textwrap.dedent(
        inspect.getsource(
            module
        )
    )

    lowered = source.casefold()

    required = (
        "foundry_project_endpoint",
        "foundry_managed_identity_client_id",
        "foundryproductionsettings",
    )

    for fragment in required:
        assert fragment in lowered

    forbidden = (
        "os.getenv",
        "os.environ",
        "from_environment",
        "azureclicredential",
        "managedidentitycredential",
        "defaultazurecredential",
        "get_token(",
        "foundryagents(",
        "run_communication",
        "communication_runner",
        "build_teams_hitl_app",
        "send_teams_message",
        "client_secret",
        "password",
        "mcp",
        ".run(",
        "asyncio.run",
    )

    for fragment in forbidden:
        assert fragment not in lowered