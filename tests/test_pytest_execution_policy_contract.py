from __future__ import annotations

import re
from pathlib import Path


PYTEST_INI = Path("pytest.ini")

LOCAL_SMOKE = Path(
    "tests/test_application_container_local_smoke_contract.py"
)


def _pytest_ini_text() -> str:
    assert PYTEST_INI.is_file()

    return PYTEST_INI.read_text(
        encoding="utf-8",
    )


def _smoke_text() -> str:
    assert LOCAL_SMOKE.is_file()

    return LOCAL_SMOKE.read_text(
        encoding="utf-8",
    )


def test_default_pytest_runner_is_deterministic_and_uses_importlib():
    text = _pytest_ini_text()

    assert re.search(
        r'(?m)^addopts\s*=\s*'
        r'--import-mode=importlib\s+'
        r'-m\s+'
        r'["\']not live and not local_container["\']'
        r'\s*$',
        text,
    )


def test_local_container_marker_is_registered_explicitly():
    text = _pytest_ini_text()

    assert re.search(
        r"(?m)^\s+local_container\s*:\s*.+$",
        text,
    )


def test_local_container_smoke_contract_is_explicitly_marked():
    text = _smoke_text()

    assert re.search(
        r"(?m)^import pytest\s*$",
        text,
    )

    assert re.search(
        r"(?m)^pytestmark\s*=\s*"
        r"pytest\.mark\.local_container\s*$",
        text,
    )