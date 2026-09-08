from __future__ import annotations

import json
import subprocess


IMAGE = (
    "ai-support-platform-sandbox:"
    "phase23-23-2-local"
)


def _docker(
    *arguments: str,
):
    return subprocess.run(
        [
            "docker",
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_local_image():
    result = _docker(
        "image",
        "inspect",
        IMAGE,
    )

    assert result.returncode == 0, (
        "certified local image absent: "
        + IMAGE
        + "\nstdout="
        + result.stdout
        + "\nstderr="
        + result.stderr
    )


def _run_python(
    code: str,
):
    _require_local_image()

    result = _docker(
        "run",
        "--rm",
        "--pull=never",
        "--network",
        "none",
        "--entrypoint",
        "python",
        IMAGE,
        "-c",
        code,
    )

    assert result.returncode == 0, (
        "container smoke failed"
        + "\nstdout="
        + result.stdout
        + "\nstderr="
        + result.stderr
    )

    return result.stdout.strip()


def test_local_image_exists_with_expected_runtime_metadata():
    _require_local_image()

    result = _docker(
        "image",
        "inspect",
        "--format",
        "{{json .}}",
        IMAGE,
    )

    assert result.returncode == 0

    metadata = json.loads(
        result.stdout
    )

    assert metadata[
        "Os"
    ] == "linux"

    assert metadata[
        "Architecture"
    ] == "amd64"

    config = metadata[
        "Config"
    ]

    assert config[
        "User"
    ] == "appuser"

    assert config[
        "Cmd"
    ] == [
        "python",
        "-m",
        "src.production_main",
    ]

    exposed_ports = (
        config.get(
            "ExposedPorts"
        )
        or {}
    )

    assert (
        "3978/tcp"
        in exposed_ports
    )


def test_container_python_version_is_exact_3_14_2():
    output = _run_python(
        "import platform; "
        "print(platform.python_version())"
    )

    assert output == "3.14.2"


def test_container_runtime_uid_is_exact_10001():
    output = _run_python(
        "import os; "
        "print(os.getuid())"
    )

    assert output == "10001"


def test_agent_framework_and_foundry_runtime_are_importable():
    output = _run_python(
        "import agent_framework; "
        "import agent_framework.foundry; "
        "import agent_framework_foundry; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_azure_identity_runtime_is_importable():
    output = _run_python(
        "import azure.identity; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_pydantic_runtime_is_importable():
    output = _run_python(
        "import pydantic; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_microsoft_teams_runtime_packages_are_importable():
    output = _run_python(
        "import microsoft_teams.api; "
        "import microsoft_teams.apps; "
        "import microsoft_teams.cards; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_azure_mgmt_compute_runtime_is_importable():
    output = _run_python(
        "import azure.mgmt.compute; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_mssql_python_runtime_and_native_dependencies_are_importable():
    output = _run_python(
        "import mssql_python; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_application_production_main_is_importable_without_live_start():
    output = _run_python(
        "import src.production_main; "
        "print('PASS')"
    )

    assert "PASS" in output


def test_dev_only_dependencies_are_absent_from_runtime_image():
    output = _run_python(
        "import importlib.util; "
        "assert importlib.util.find_spec('pytest') is None; "
        "assert importlib.util.find_spec('pytest_asyncio') is None; "
        "assert importlib.util.find_spec('azure.functions') is None; "
        "print('PASS')"
    )

    assert "PASS" in output