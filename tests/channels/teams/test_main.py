from dataclasses import (
    dataclass,
)

import pytest

from src.channels.teams import (
    main as teams_main,
)


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
    fake_settings = object()
    fake_reader = object()

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

    received_composition = []

    def fake_build(
        settings,
        *,
        azure_vm_power_state_reader,
    ):
        received_composition.append(
            (
                settings,
                azure_vm_power_state_reader,
            )
        )

        return (
            fake_bootstrap
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

    assert (
        received_composition
        == [
            (
                fake_settings,
                fake_reader,
            )
        ]
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
