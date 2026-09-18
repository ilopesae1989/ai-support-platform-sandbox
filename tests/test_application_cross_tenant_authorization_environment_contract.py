from __future__ import annotations

import json
import re

from pathlib import Path


FOUNDATION = Path(
    "infra/application-foundation.bicep"
)

APPLICATION_HOST = Path(
    "infra/container-apps/application-host.bicep"
)

PARAMETERS = Path(
    "infra/application-foundation.sandbox.parameters.json"
)


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


EXPECTED_MAPPING = [
    {
        "sourceTenantId": SOURCE_TENANT_ID,
        "sourceUserObjectId": SOURCE_USER_OBJECT_ID,
        "targetTenantId": AUTHORIZATION_TENANT_ID,
        "targetUserObjectId": AUTHORIZATION_USER_OBJECT_ID,
    }
]


EXPECTED_MAPPING_JSON = json.dumps(
    EXPECTED_MAPPING,
    separators=(",", ":"),
)


def _compact(
    path: Path,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        path.read_text(
            encoding="utf-8"
        ),
    )


def test_foundation_declares_exact_cross_tenant_authorization_parameters():
    text = FOUNDATION.read_text(
        encoding="utf-8"
    )

    assert re.search(
        r"^param\s+"
        r"teamsAuthorizationDirectoryTenantId\s+"
        r"string\s*$",
        text,
        flags=re.MULTILINE,
    )

    assert re.search(
        r"^param\s+"
        r"teamsAuthorizationIdentityMappingsJson\s+"
        r"string\s*$",
        text,
        flags=re.MULTILINE,
    )


def test_foundation_passes_exact_authorization_parameters_to_host_module():
    compact = _compact(
        FOUNDATION
    )

    assert (
        "teamsAuthorizationDirectoryTenantId: "
        "teamsAuthorizationDirectoryTenantId"
        in compact
    )

    assert (
        "teamsAuthorizationIdentityMappingsJson: "
        "teamsAuthorizationIdentityMappingsJson"
        in compact
    )


def test_application_host_declares_exact_authorization_parameters():
    text = APPLICATION_HOST.read_text(
        encoding="utf-8"
    )

    assert re.search(
        r"^param\s+"
        r"teamsAuthorizationDirectoryTenantId\s+"
        r"string\s*$",
        text,
        flags=re.MULTILINE,
    )

    assert re.search(
        r"^param\s+"
        r"teamsAuthorizationIdentityMappingsJson\s+"
        r"string\s*$",
        text,
        flags=re.MULTILINE,
    )


def test_application_host_projects_exact_runtime_environment_variables():
    compact = _compact(
        APPLICATION_HOST
    )

    assert re.search(
        r"name:\s*"
        r"'TEAMS_AUTHORIZATION_DIRECTORY_TENANT_ID'"
        r"\s+value:\s*"
        r"teamsAuthorizationDirectoryTenantId",
        compact,
    )

    assert re.search(
        r"name:\s*"
        r"'TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON'"
        r"\s+value:\s*"
        r"teamsAuthorizationIdentityMappingsJson",
        compact,
    )

    assert (
        compact.count(
            "TEAMS_AUTHORIZATION_DIRECTORY_TENANT_ID"
        )
        == 1
    )

    assert (
        compact.count(
            "TEAMS_AUTHORIZATION_IDENTITY_MAPPINGS_JSON"
        )
        == 1
    )


def test_sandbox_parameters_contain_exact_authorization_directory():
    payload = json.loads(
        PARAMETERS.read_text(
            encoding="utf-8"
        )
    )

    parameters = payload[
        "parameters"
    ]

    assert (
        parameters[
            "teamsAuthorizationDirectoryTenantId"
        ][
            "value"
        ]
        == AUTHORIZATION_TENANT_ID
    )

    assert (
        parameters[
            "teamsChannelTenantId"
        ][
            "value"
        ]
        == SOURCE_TENANT_ID
    )

    assert (
        parameters[
            "teamsAuthorizationDirectoryTenantId"
        ][
            "value"
        ]
        != parameters[
            "teamsChannelTenantId"
        ][
            "value"
        ]
    )


def test_sandbox_parameters_contain_exact_explicit_identity_mapping():
    payload = json.loads(
        PARAMETERS.read_text(
            encoding="utf-8"
        )
    )

    raw = payload[
        "parameters"
    ][
        "teamsAuthorizationIdentityMappingsJson"
    ][
        "value"
    ]

    assert isinstance(
        raw,
        str,
    )

    assert raw == EXPECTED_MAPPING_JSON

    parsed = json.loads(
        raw
    )

    assert parsed == EXPECTED_MAPPING


def test_mapping_contains_no_identity_inference_attributes():
    payload = json.loads(
        PARAMETERS.read_text(
            encoding="utf-8"
        )
    )

    raw = payload[
        "parameters"
    ][
        "teamsAuthorizationIdentityMappingsJson"
    ][
        "value"
    ]

    lowered = raw.casefold()

    forbidden = (
        "mail",
        "email",
        "upn",
        "userprincipalname",
        "user_principal_name",
        "displayname",
        "display_name",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_authorization_environment_contract_is_secret_free():
    combined = "\n".join(
        (
            FOUNDATION.read_text(
                encoding="utf-8"
            ),
            APPLICATION_HOST.read_text(
                encoding="utf-8"
            ),
            PARAMETERS.read_text(
                encoding="utf-8"
            ),
        )
    ).casefold()

    forbidden = (
        "teams_authorization_identity_mapping_secret",
        "teams_authorization_identity_mappings_secret",
        "authorization_identity_secret",
        "secretref:",
    )

    for fragment in forbidden:
        assert fragment not in combined