from pathlib import Path


ACA_BICEP_PATH = Path(
    "platform/azure-mcp/"
    "azmcp-foundry-aca-mi/"
    "infra/modules/"
    "aca-infrastructure.bicep"
)


PINNED_AZURE_MCP_IMAGE = (
    "mcr.microsoft.com/azure-sdk/"
    "azure-mcp@sha256:"
    "2c4387a13a925b38a2592bca1f16d7d13c377332419b2db020697138ccc41268"
)


def _read() -> str:
    assert ACA_BICEP_PATH.exists()

    return ACA_BICEP_PATH.read_text(
        encoding="utf-8"
    )


def test_azure_mcp_image_does_not_use_latest_tag():
    text = _read()

    assert (
        "mcr.microsoft.com/azure-sdk/azure-mcp:latest"
        not in text
    )


def test_azure_mcp_image_is_pinned_to_certified_amd64_digest():
    text = _read()

    assert PINNED_AZURE_MCP_IMAGE in text
