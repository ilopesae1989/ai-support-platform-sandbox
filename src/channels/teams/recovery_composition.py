"""Attach recovery to the existing host persistence pair without opening it."""
from dataclasses import replace

from src.channels.teams.bootstrap import TeamsHitlBootstrap
from src.runtime.incident_continuation_recovery import IncidentContinuationRecovery
from src.runtime.incident_continuation_recovery_runner import (
    ContinuationRecoveryPolicy, IncidentContinuationRecoveryRunner,
)


def attach_continuation_recovery(bootstrap, policy: ContinuationRecoveryPolicy | None):
    if policy is None:
        return bootstrap
    if not isinstance(bootstrap, TeamsHitlBootstrap):
        raise TypeError("Recovery requires the composed host bootstrap.")
    if bootstrap.continuation_recovery_runner is not None:
        raise ValueError("Recovery is already attached to this host.")
    for method in ("list_stale_claims", "recover_stale_before_approval"):
        if not callable(getattr(bootstrap.continuation_store, method, None)):
            raise TypeError("The host continuation store does not support recovery.")
    return replace(bootstrap, continuation_recovery_runner=IncidentContinuationRecoveryRunner(
        recovery=IncidentContinuationRecovery(
            continuation_store=bootstrap.continuation_store, approval_store=bootstrap.store,
        ), policy=policy,
    ))
