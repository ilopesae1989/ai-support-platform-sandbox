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
class FakeBootstrap:
    app: FakeApp


@pytest.mark.asyncio
async def test_run_teams_hitl_app_starts_bootstrapped_app(
    monkeypatch,
):
    fake_settings = object()

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

    received_settings = []

    def fake_build(
        settings,
    ):
        received_settings.append(
            settings
        )

        return (
            fake_bootstrap
        )

    monkeypatch.setattr(
        teams_main,
        "build_teams_hitl_app",
        fake_build,
    )

    await (
        teams_main
        .run_teams_hitl_app()
    )

    assert (
        received_settings
        == [
            fake_settings
        ]
    )

    assert (
        fake_app.start_called
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