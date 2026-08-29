from pathlib import Path


ACA_BICEP_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/modules/"
    "aca-infrastructure.bicep"
)

MAIN_BICEP_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/"
    "main.bicep"
)

PARAMETERS_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/"
    "main.parameters.json"
)


PARAM_NAME = (
    "azureMcpDangerouslyDisableElicitation"
)

FLAG = (
    "--dangerously-disable-elicitation"
)


def _read(path: Path) -> str:
    assert path.exists()

    return path.read_text(
        encoding="utf-8"
    )


def _executable_text(
    path: Path,
) -> str:
    """
    Excluye comentarios Bicep de línea completa.

    Las comprobaciones de seguridad validan
    configuración ejecutable, no comentarios.
    """

    lines = []

    for line in _read(path).splitlines():

        if line.lstrip().startswith(
            "//"
        ):
            continue

        lines.append(
            line
        )

    return "\n".join(
        lines
    )


def test_generic_parameter_file_does_not_enable_elicitation_bypass():
    """
    El parameter file compartido no puede convertir
    el bypass en comportamiento implícito.
    """

    text = _read(
        PARAMETERS_PATH
    )

    assert PARAM_NAME not in text
    assert FLAG not in text


def test_module_elicitation_bypass_is_disabled_by_default():
    """
    Cualquier consumidor nuevo del módulo conserva
    elicitation salvo opt-in explícito.
    """

    text = _executable_text(
        ACA_BICEP_PATH
    )

    assert (
        "param "
        + PARAM_NAME
        + " bool = false"
        in text
    )


def test_module_disable_elicitation_flag_is_conditional():
    """
    El flag inseguro puede existir únicamente en
    una rama gobernada por el parámetro booleano.

    Nunca puede añadirse incondicionalmente a
    baseArgs.
    """

    text = _executable_text(
        ACA_BICEP_PATH
    )

    assert (
        f"'{FLAG}'"
        in text
    )

    assert (
        PARAM_NAME + " ?"
        in text
    )

    base_start = text.find(
        "var baseArgs = ["
    )

    assert base_start >= 0

    base_end = text.find(
        "]",
        base_start,
    )

    assert base_end >= 0

    base_args = text[
        base_start:
        base_end + 1
    ]

    assert (
        f"'{FLAG}'"
        not in base_args
    )


def test_main_exposes_safe_default_and_forwards_to_aca_module():
    """
    main.bicep mantiene false por defecto y sólo
    transmite una decisión explícita al módulo ACA.
    """

    text = _executable_text(
        MAIN_BICEP_PATH
    )

    assert (
        "param "
        + PARAM_NAME
        + " bool = false"
        in text
    )

    assert (
        PARAM_NAME
        + ": "
        + PARAM_NAME
        in text
    )


def test_legacy_elicitation_names_are_absent_from_production_iac():
    """
    El nombre observado inicialmente no corresponde
    al CLI real de Azure.Mcp.Server 3.0.0-beta.35.

    La IaC productiva no puede conservar ni el
    parámetro legacy ni el flag legacy.
    """

    main_text = _executable_text(
        MAIN_BICEP_PATH
    )

    module_text = _executable_text(
        ACA_BICEP_PATH
    )

    for production_text in (
        main_text,
        module_text,
    ):
        assert (
            "azureMcpInsecureDisableElicitation"
            not in production_text
        )

        assert (
            "'--insecure-disable-elicitation'"
            not in production_text
        )
