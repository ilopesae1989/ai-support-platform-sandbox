from __future__ import annotations

import re
from pathlib import Path


RUNTIME_REQUIREMENTS = Path(
    "requirements-runtime.txt"
)

DOCKERFILE = Path(
    "Dockerfile"
)


CERTIFIED_RUNTIME_REQUIREMENTS = {
    "agent-framework-core==1.13.0",
    "agent-framework-foundry==1.10.4",
    "azure-identity==1.25.3",
    "pydantic==2.13.4",
    "microsoft-teams-api==2.0.14",
    "microsoft-teams-cards==2.0.14",
    "microsoft-teams-apps==2.0.14",
    "azure-mgmt-compute==38.3.0",
    "mssql-python==1.14.0",
}


def _runtime_lines():
    assert RUNTIME_REQUIREMENTS.is_file()

    return [
        line.strip()
        for line in RUNTIME_REQUIREMENTS.read_text(
            encoding="utf-8"
        ).splitlines()
        if (
            line.strip()
            and not line.strip().startswith("#")
        )
    ]


def _dockerfile_text():
    assert DOCKERFILE.is_file()

    return DOCKERFILE.read_text(
        encoding="utf-8"
    )


def _dockerfile_lines():
    return [
        line.strip()
        for line in _dockerfile_text().splitlines()
        if (
            line.strip()
            and not line.strip().startswith("#")
        )
    ]


def test_runtime_requirements_manifest_exists():
    assert RUNTIME_REQUIREMENTS.is_file()


def test_runtime_requirements_are_exact_certified_direct_set():
    lines = _runtime_lines()

    assert len(
        lines
    ) == 9

    assert set(
        lines
    ) == CERTIFIED_RUNTIME_REQUIREMENTS

    for line in lines:
        assert re.fullmatch(
            r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+",
            line,
        )


def test_runtime_requirements_exclude_dev_only_dependencies():
    lowered = "\n".join(
        _runtime_lines()
    ).casefold()

    forbidden = (
        "pytest",
        "pytest-asyncio",
        "azure-functions",
    )

    for dependency in forbidden:
        assert dependency not in lowered


def test_application_dockerfile_exists():
    assert DOCKERFILE.is_file()


def test_dockerfile_requires_external_digest_pinned_python_base_image():
    lines = _dockerfile_lines()

    arg_lines = [
        line
        for line in lines
        if line.casefold().startswith(
            "arg "
        )
    ]

    from_lines = [
        line
        for line in lines
        if line.casefold().startswith(
            "from "
        )
    ]

    assert arg_lines == [
        "ARG PYTHON_BASE_IMAGE_DIGEST_REF"
    ]

    assert from_lines == [
        "FROM ${PYTHON_BASE_IMAGE_DIGEST_REF}"
    ]

    assert "=" not in arg_lines[0]

    lowered = "\n".join(
        lines
    ).casefold()

    assert "latest" not in lowered

    assert "python:3" not in lowered


def test_dockerfile_installs_certified_mssql_linux_libraries_only():
    text = _dockerfile_text()

    compact = " ".join(
        line.strip().rstrip("\\").strip()
        for line in text.splitlines()
    ).casefold()

    assert "apt-get update" in compact
    assert "apt-get install" in compact
    assert "--no-install-recommends" in compact

    required = (
        "libltdl7",
        "libkrb5-3",
        "libgssapi-krb5-2",
    )

    for package in required:
        assert package in compact

    assert "rm -rf /var/lib/apt/lists/*" in compact

    forbidden = (
        "unixodbc",
        "msodbcsql",
        "odbcinst",
    )

    for package in forbidden:
        assert package not in compact


def test_dockerfile_installs_runtime_manifest_and_never_dev_manifest():
    lines = _dockerfile_lines()

    assert (
        "COPY requirements-runtime.txt "
        "/app/requirements-runtime.txt"
    ) in lines

    compact = " ".join(
        lines
    )

    assert (
        "python -m pip install "
        "--no-cache-dir "
        "-r /app/requirements-runtime.txt"
    ) in compact

    lowered = compact.casefold()

    assert "requirements-dev.txt" not in lowered
    assert "pytest" not in lowered
    assert "pytest-asyncio" not in lowered


def test_dockerfile_copies_only_application_runtime_surface():
    lines = _dockerfile_lines()

    accepted_source_copy = {
        "COPY src /app/src",
        "COPY src/ /app/src/",
    }

    assert any(
        line in accepted_source_copy
        for line in lines
    )

    lowered = "\n".join(
        lines
    ).casefold()

    forbidden = (
        "copy . ",
        "copy ./ ",
        "add . ",
        "add ./ ",
        "copy tests",
        "add tests",
    )

    for fragment in forbidden:
        assert fragment not in lowered


def test_dockerfile_runs_as_dedicated_non_root_user():
    lines = _dockerfile_lines()

    creation_lines = [
        line
        for line in lines
        if (
            "useradd" in line.casefold()
            or "adduser" in line.casefold()
        )
    ]

    assert len(
        creation_lines
    ) == 1

    creation = creation_lines[0].casefold()

    assert "appuser" in creation
    assert "10001" in creation

    user_lines = [
        line
        for line in lines
        if line.casefold().startswith(
            "user "
        )
    ]

    assert user_lines == [
        "USER appuser"
    ]


def test_dockerfile_has_exact_application_workdir_port_and_process_command():
    lines = _dockerfile_lines()

    assert (
        "WORKDIR /app"
        in lines
    )

    assert (
        "EXPOSE 3978"
        in lines
    )

    assert (
        'CMD ["python", "-m", "src.production_main"]'
        in lines
    )

    forbidden_shell_commands = (
        "cmd python ",
        "entrypoint python ",
    )

    lowered = "\n".join(
        lines
    ).casefold()

    for fragment in forbidden_shell_commands:
        assert fragment not in lowered


def test_dockerfile_does_not_bake_runtime_configuration_or_secrets():
    lowered = _dockerfile_text().casefold()

    sensitive_fragments = (
        "foundry_project_endpoint",
        "foundry_managed_identity_client_id",
        "managed_identity_client_id",
        "azure_sql_managed_identity_client_id",
        "azure_vm_reader_managed_identity_client_id",
        "azure_sql_server",
        "azure_sql_database",
        "teams_channel_tenant_id",
        "teams_hitl_approver_aad_object_id",
        "client_secret",
        "password",
        "connection_string",
        "copy .env",
        "add .env",
    )

    for fragment in sensitive_fragments:
        assert fragment not in lowered