import inspect

from dataclasses import (
    dataclass,
)

from types import SimpleNamespace

from unittest.mock import (
    AsyncMock,
    Mock,
    create_autospec,
)

import pytest

from src.channels.teams import (
    main as teams_main,
)


BOT_TENANT_ID = "11111111-1111-4111-8111-111111111111"
CHANNEL_TENANT_ID = "22222222-2222-4222-8222-222222222222"


@dataclass
class FakeApp:
    start_called: bool = False

    async def start(
        self,
    ) -> None:
        self.start_called = True


@dataclass
class FakeContinuationWorker:
    run_called: bool = False

    async def run(
        self,
        *,
        stop_event,
    ) -> None:
        self.run_called = True

        await stop_event.wait()

@dataclass
class FakeBootstrap:
    app: FakeApp


@pytest.mark.asyncio
async def test_run_teams_hitl_app_starts_bootstrapped_app(
    monkeypatch,
):
    fake_settings = SimpleNamespace(
        bot_tenant_id=BOT_TENANT_ID,
        teams_channel_tenant_id=CHANNEL_TENANT_ID,
    )
    fake_reader = object()
    fake_membership_checker = object()

    fake_app = (
        FakeApp()
    )

    fake_bootstrap = (
        FakeBootstrap(
            app=(
                fake_app
            )
        )
    )

    monkeypatch.setattr(
        teams_main.TeamsHitlSettings,
        "from_environment",
        lambda: (
            fake_settings
        ),
    )

    monkeypatch.setattr(
        teams_main,
        "build_local_azure_vm_power_state_reader",
        lambda: fake_reader,
    )

    membership_factory = Mock(
        return_value=fake_membership_checker,
    )

    monkeypatch.setattr(
        teams_main,
        "build_local_teams_membership_checker",
        membership_factory,
    )

    fake_build = create_autospec(
        teams_main.build_teams_hitl_app,
        return_value=fake_bootstrap,
    )

    monkeypatch.setattr(
        teams_main,
        "build_teams_hitl_app",
        fake_build,
    )

    fake_worker = (
        FakeContinuationWorker()
    )

    fake_bootstrap.continuation_worker = (
        fake_worker
    )

    await (
        teams_main
        .run_teams_hitl_app()
    )

    membership_factory.assert_called_once_with(
        tenant_id=CHANNEL_TENANT_ID,
    )

    fake_build.assert_called_once_with(
        fake_settings,
        membership_checker=fake_membership_checker,
        azure_vm_power_state_reader=fake_reader,
    )

    assert (
        fake_app.start_called
        is True
    )

    assert (
        fake_worker.run_called
        is True
    )
def test_main_uses_asyncio_run(
    monkeypatch,
):
    captured = []

    async def fake_runner():
        return None

    def fake_asyncio_run(
        awaitable,
    ):
        captured.append(
            awaitable
        )

        # Cerramos el coroutine porque estamos
        # sustituyendo asyncio.run durante el test.
        awaitable.close()

    monkeypatch.setattr(
        teams_main,
        "run_teams_hitl_app",
        fake_runner,
    )

    monkeypatch.setattr(
        teams_main.asyncio,
        "run",
        fake_asyncio_run,
    )

    teams_main.main()

    assert (
        len(
            captured
        )
        == 1
    )


def test_local_reader_factory_injects_azure_cli_credential(
    monkeypatch,
):
    credential = object()
    reader = object()

    credential_calls = []
    reader_calls = []

    def fake_credential():
        credential_calls.append(
            True
        )
        return credential

    def fake_reader(
        *,
        credential,
    ):
        reader_calls.append(
            credential
        )
        return reader

    monkeypatch.setattr(
        teams_main,
        "AzureCliCredential",
        fake_credential,
    )

    monkeypatch.setattr(
        teams_main,
        "AzureSdkVmPowerStateReader",
        fake_reader,
    )

    result = (
        teams_main
        .build_local_azure_vm_power_state_reader()
    )

    assert result is reader

    assert credential_calls == [
        True
    ]

    assert reader_calls == [
        credential
    ]


def test_local_membership_factory_uses_async_cli_without_token_or_http(
    monkeypatch,
):
    assert inspect.iscoroutinefunction(
        teams_main.AsyncAzureCliCredential.get_token
    )

    credential = SimpleNamespace(
        get_token=AsyncMock(
            side_effect=AssertionError(
                "No token during composition."
            ),
        ),
    )
    transport = SimpleNamespace(
        post_json=AsyncMock(
            side_effect=AssertionError(
                "No HTTP during composition."
            ),
        ),
    )
    credential_factory = Mock(return_value=credential)
    transport_factory = Mock(return_value=transport)
    client_type = teams_main.MicrosoftGraphGroupMembershipClient
    client_factory = Mock(wraps=client_type)

    monkeypatch.setattr(
        teams_main,
        "AsyncAzureCliCredential",
        credential_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "UrllibGraphJsonTransport",
        transport_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "MicrosoftGraphGroupMembershipClient",
        client_factory,
    )

    result = teams_main.build_local_teams_membership_checker(
        tenant_id=CHANNEL_TENANT_ID,
    )

    assert isinstance(result, client_type)
    credential_factory.assert_called_once_with(
        tenant_id=CHANNEL_TENANT_ID,
    )
    transport_factory.assert_called_once_with()
    client_factory.assert_called_once_with(
        credential=credential,
        transport=transport,
    )
    credential.get_token.assert_not_called()
    transport.post_json.assert_not_called()


@pytest.mark.parametrize(
    "tenant_id",
    (
        None,
        42,
        "",
        " ",
        " " + CHANNEL_TENANT_ID,
        CHANNEL_TENANT_ID + " ",
    ),
    ids=(
        "missing",
        "non-string",
        "empty",
        "whitespace",
        "leading-space",
        "trailing-space",
    ),
)
def test_local_membership_factory_rejects_invalid_tenant_before_construction(
    monkeypatch,
    tenant_id,
):
    credential_factory = Mock(
        side_effect=AssertionError(
            "No credential for invalid tenant."
        ),
    )
    transport_factory = Mock(
        side_effect=AssertionError(
            "No transport for invalid tenant."
        ),
    )
    monkeypatch.setattr(
        teams_main,
        "AsyncAzureCliCredential",
        credential_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "UrllibGraphJsonTransport",
        transport_factory,
    )

    with pytest.raises(
        teams_main.TeamsHitlConfigurationError,
        match="tenant_id",
    ):
        teams_main.build_local_teams_membership_checker(
            tenant_id=tenant_id,
        )

    credential_factory.assert_not_called()
    transport_factory.assert_not_called()


@pytest.mark.asyncio
async def test_run_rejects_invalid_membership_tenant_before_bootstrap(
    monkeypatch,
):
    settings = SimpleNamespace(
        bot_tenant_id=BOT_TENANT_ID,
        teams_channel_tenant_id="",
    )
    monkeypatch.setattr(
        teams_main.TeamsHitlSettings,
        "from_environment",
        lambda: settings,
    )
    credential_factory = Mock(
        side_effect=AssertionError("No credential for invalid tenant."),
    )
    reader_factory = Mock()
    bootstrap_factory = create_autospec(
        teams_main.build_teams_hitl_app,
    )
    monkeypatch.setattr(
        teams_main,
        "AsyncAzureCliCredential",
        credential_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "build_local_azure_vm_power_state_reader",
        reader_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "build_teams_hitl_app",
        bootstrap_factory,
    )

    with pytest.raises(
        teams_main.TeamsHitlConfigurationError,
        match="tenant_id",
    ):
        await teams_main.run_teams_hitl_app()

    credential_factory.assert_not_called()
    reader_factory.assert_not_called()
    bootstrap_factory.assert_not_called()


@pytest.mark.asyncio
async def test_run_stops_on_membership_credential_construction_failure(
    monkeypatch,
):
    settings = SimpleNamespace(
        bot_tenant_id=BOT_TENANT_ID,
        teams_channel_tenant_id=CHANNEL_TENANT_ID,
    )
    monkeypatch.setattr(
        teams_main.TeamsHitlSettings,
        "from_environment",
        lambda: settings,
    )
    credential_factory = Mock(
        side_effect=RuntimeError("Graph credential unavailable."),
    )
    reader_factory = Mock()
    bootstrap_factory = create_autospec(
        teams_main.build_teams_hitl_app,
    )
    monkeypatch.setattr(
        teams_main,
        "AsyncAzureCliCredential",
        credential_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "build_local_azure_vm_power_state_reader",
        reader_factory,
    )
    monkeypatch.setattr(
        teams_main,
        "build_teams_hitl_app",
        bootstrap_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="Graph credential unavailable",
    ):
        await teams_main.run_teams_hitl_app()

    credential_factory.assert_called_once_with(
        tenant_id=CHANNEL_TENANT_ID,
    )
    reader_factory.assert_not_called()
    bootstrap_factory.assert_not_called()
