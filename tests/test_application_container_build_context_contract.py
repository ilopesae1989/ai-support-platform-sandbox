from pathlib import Path


DOCKERIGNORE = Path(
    ".dockerignore"
)


EXPECTED_RULES = [
    "*",
    "!src/",
    "!src/**",
    "!requirements-runtime.txt",
    "!Dockerfile",
    "!.dockerignore",
]


def _rules():
    assert DOCKERIGNORE.is_file()

    return [
        line.strip()
        for line in DOCKERIGNORE.read_text(
            encoding="utf-8"
        ).splitlines()
        if (
            line.strip()
            and not line.lstrip().startswith("#")
        )
    ]


def test_dockerignore_exists():
    assert DOCKERIGNORE.is_file()


def test_dockerignore_is_exact_deny_all_allowlist():
    assert _rules() == EXPECTED_RULES


def test_dockerignore_denies_everything_before_exceptions():
    rules = _rules()

    assert rules[0] == "*"

    assert all(
        rule.startswith("!")
        for rule in rules[1:]
    )


def test_dockerignore_allows_only_required_build_inputs():
    rules = set(
        _rules()[1:]
    )

    assert rules == {
        "!src/",
        "!src/**",
        "!requirements-runtime.txt",
        "!Dockerfile",
        "!.dockerignore",
    }


def test_dockerignore_has_no_sensitive_or_broad_allow_exceptions():
    lowered = {rule.casefold() for rule in _rules()}

    forbidden_allow_rules = (
        "!.git",
        "!.git/",
        "!.venv",
        "!.venv/",
        "!venv",
        "!venv/",
        "!tests",
        "!tests/",
        "!.env",
        "!.env.*",
        "!docs",
        "!docs/",
        "!scripts",
        "!scripts/",
        "!infra",
        "!infra/",
        "!platform",
        "!platform/",
        "!requirements-dev.txt",
        "!.",
        "!./",
        "!**",
        "!**/*",
    )

    for rule in forbidden_allow_rules:
        assert rule not in lowered


def test_dockerignore_explicitly_preserves_dockerfile_copy_sources():
    rules = _rules()

    assert "!src/" in rules
    assert "!src/**" in rules
    assert "!requirements-runtime.txt" in rules