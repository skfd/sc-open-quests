"""tools/spend_breaker.py: pricing, the gate, the trip and its latch. No network: estimator and cut are faked."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import spend_breaker as sb  # noqa: E402

ENV = {"CLOUDFLARE_API_TOKEN": "t", "CLOUDFLARE_ACCOUNT_ID": "a"}


def fake_estimator(a=0, b=0, gb=1.0):
    def est(env, extra_a=0, extra_b=0):
        p = sb.price(a + extra_a, b + extra_b, int(gb * 1e9))
        p.update(window="month", at="2026-11-19T15:00:00+00:00")
        return p
    return est


def failing_estimator(env, extra_a=0, extra_b=0):
    raise RuntimeError("analytics down")


class Cut:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, env, enabled):
        self.calls.append(enabled)
        if self.fail:
            raise RuntimeError("api said no")


# ---- pricing ----

def test_free_tier_costs_nothing():
    assert sb.price(1_000_000, 10_000_000, 10 * 10**9)["usd"] == 0


def test_rounds_up_to_the_next_unit():
    p = sb.price(1_000_001, 10_000_001, int(10.1e9))
    assert p["usd_a"] == 4.5 and p["usd_b"] == 0.36 and p["usd_storage"] > 0


def test_unknown_action_is_priced_as_class_a():
    groups = [{"dimensions": {"actionType": "SomethingNew"}, "sum": {"requests": 5}},
              {"dimensions": {"actionType": "GetObject"}, "sum": {"requests": 7}},
              {"dimensions": {"actionType": "DeleteObject"}, "sum": {"requests": 9}}]
    store = [{"dimensions": {"bucketName": "x"}, "max": {"payloadSize": 10, "metadataSize": 1}},
             {"dimensions": {"bucketName": "x"}, "max": {"payloadSize": 30, "metadataSize": 2}},
             {"dimensions": {"bucketName": "y"}, "max": {"payloadSize": 5, "metadataSize": 0}}]
    assert sb.tally(groups, store) == (5, 7, 32 + 5)


# ---- gate ----

def test_gate_passes_under_the_line(tmp_path):
    sb.gate(planned_class_a=5000, env=ENV, estimator=fake_estimator(), latch=tmp_path / "l.json")


def test_gate_refuses_a_run_that_would_cross_the_line(tmp_path):
    # $36 spent; a run planning 2M more writes would be about $45
    with pytest.raises(sb.Tripped, match="line"):
        sb.gate(planned_class_a=2_000_000, env=ENV, estimator=fake_estimator(a=9_000_000),
                latch=tmp_path / "l.json")


def test_gate_refuses_while_latched(tmp_path):
    latch = tmp_path / "l.json"
    sb.write_latch({"tripped_at": "x", "reason": "test"}, latch)
    with pytest.raises(sb.Tripped, match="--reset"):
        sb.gate(env=ENV, estimator=fake_estimator(), latch=latch)


def test_unreadable_latch_counts_as_tripped(tmp_path):
    latch = tmp_path / "l.json"
    latch.write_text("{not json", encoding="utf-8")
    with pytest.raises(sb.Tripped):
        sb.gate(env=ENV, estimator=fake_estimator(), latch=latch)


def test_analytics_failure_lenient_goes_on_strict_refuses(tmp_path):
    latch = tmp_path / "l.json"
    sb.gate(env=ENV, estimator=failing_estimator, latch=latch)
    with pytest.raises(sb.Tripped, match="blind"):
        sb.gate(env=ENV, estimator=failing_estimator, latch=latch, strict=True)


# ---- the hourly check ----

def test_check_under_the_line_changes_nothing(tmp_path):
    latch, cut = tmp_path / "l.json", Cut()
    assert sb.check(env=ENV, estimator=fake_estimator(), latch=latch, cut=cut) == 0
    assert not latch.exists() and cut.calls == []


def test_check_trips_cuts_the_domain_and_latches(tmp_path):
    latch, cut = tmp_path / "l.json", Cut()
    assert sb.check(env=ENV, estimator=fake_estimator(a=12_000_000), latch=latch, cut=cut) == 2
    assert cut.calls == [False]
    held = sb.latched(latch)
    assert held["domain_disabled"] is True and "$49.50" in held["reason"]
    # the latch holds after spend falls back (a new month): only --reset clears it
    assert sb.check(env=ENV, estimator=fake_estimator(), latch=latch, cut=cut) == 2
    assert cut.calls == [False]
    with pytest.raises(sb.Tripped):
        sb.gate(env=ENV, estimator=fake_estimator(), latch=latch)


def test_dry_run_trip_touches_nothing(tmp_path):
    latch, cut = tmp_path / "l.json", Cut()
    assert sb.check(dry_run=True, env=ENV, estimator=fake_estimator(b=200_000_000), latch=latch, cut=cut) == 2
    assert not latch.exists() and cut.calls == []


def test_failed_cut_keeps_the_latch_and_is_retried(tmp_path):
    latch = tmp_path / "l.json"
    with pytest.raises(RuntimeError, match="api said no"):
        sb.check(env=ENV, estimator=fake_estimator(a=12_000_000), latch=latch, cut=Cut(fail=True))
    held = sb.latched(latch)
    assert held and held["domain_disabled"] is False
    cut = Cut()
    assert sb.check(env=ENV, estimator=fake_estimator(), latch=latch, cut=cut) == 2
    assert cut.calls == [False] and sb.latched(latch)["domain_disabled"] is True


def test_lenient_gate_survives_any_analytics_error(tmp_path):
    def broken(env, extra_a=0, extra_b=0):
        return [][0]          # an IndexError, as from an empty accounts list
    sb.gate(env=ENV, estimator=broken, latch=tmp_path / "l.json")
    with pytest.raises(sb.Tripped):
        sb.gate(env=ENV, estimator=broken, latch=tmp_path / "l.json", strict=True)
