import json

import pytest

from src.config.continuation_recovery import parse_continuation_recovery_policy as parse
from src.runtime.incident_continuation_recovery_runner import ContinuationRecoveryPolicy


ENABLED = dict(schema="continuation-recovery-v1", enabled=True, min_claim_age_seconds=300,
               interval_seconds=60, batch_size=25, max_batches_per_cycle=4)


def environment(value):
    return {"CONTINUATION_RECOVERY_JSON": json.dumps(value)}


def test_absence_and_explicit_disabled_do_not_enable_recovery():
    assert parse({}) is None
    assert parse(environment(dict(schema="continuation-recovery-v1", enabled=False))) is None
    assert parse(environment(ENABLED)) == ContinuationRecoveryPolicy(300, 60, 25, 4)


@pytest.mark.parametrize("value", [None, "", " ", "{", "[]", "null", "true", '{"private-config":',
    '{"schema":"continuation-recovery-v1","enabled":false,"enabled":true}'])
def test_invalid_raw_configuration_is_rejected_without_echo(value):
    with pytest.raises(ValueError) as error:
        parse({"CONTINUATION_RECOVERY_JSON": value})
    assert "private-config" not in str(error.value)


@pytest.mark.parametrize("change", [dict(schema="future"), dict(enabled=1), dict(enabled="true"),
    dict(enabled=False), dict(tenant_id="unexpected"), dict(interval_seconds=None)])
def test_unknown_schema_fields_and_non_boolean_enable_are_rejected(change):
    with pytest.raises(ValueError):
        parse(environment(ENABLED | change))


@pytest.mark.parametrize("field", ["min_claim_age_seconds", "interval_seconds", "batch_size", "max_batches_per_cycle"])
def test_policy_requires_every_field_and_exact_bounded_integer(field):
    incomplete = dict(ENABLED)
    del incomplete[field]
    with pytest.raises(ValueError):
        parse(environment(incomplete))
    for invalid in (True, False, 0, -1, 1.0, "1", 86401):
        with pytest.raises(ValueError):
            parse(environment(ENABLED | {field: invalid}))


@pytest.mark.parametrize("field", ["batch_size", "max_batches_per_cycle"])
def test_work_count_cap_is_one_hundred(field):
    assert getattr(parse(environment(ENABLED | {field: 100})), field) == 100
    with pytest.raises(ValueError):
        parse(environment(ENABLED | {field: 101}))


def test_disabled_configuration_does_not_hide_unknown_fields():
    with pytest.raises(ValueError):
        parse(environment(dict(schema="continuation-recovery-v1", enabled=False, unexpected=1)))
    with pytest.raises(TypeError):
        parse(None)
