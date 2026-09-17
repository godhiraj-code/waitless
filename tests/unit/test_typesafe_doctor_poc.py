"""Tests for the standalone TypeSafe doctor proof of concept."""

import copy
import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from examples.typesafe_doctor.evaluate import evaluate_manifest
from examples.typesafe_doctor.poc import (
    Investigation,
    ProviderDecision,
    ProviderError,
    ScriptedProvider,
    TypeSafeProvider,
    _validate_decision,
    build_analysis_input,
    corrected_baseline,
    legacy_investigations,
    run_provider,
)


FIXTURES = Path(__file__).parents[2] / "examples" / "typesafe_doctor" / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_allowlist_excludes_planted_secrets_and_keeps_input_unchanged():
    document = load_fixture("network_only.json")
    original = copy.deepcopy(document)

    analysis = build_analysis_input(document)
    serialized = json.dumps(analysis.state, sort_keys=True)

    assert analysis.eligible == (Investigation.INSPECT_NETWORK,)
    assert "TOP_SECRET" not in serialized
    assert "private.example.test" not in serialized
    assert "accounts/123" not in serialized
    assert "details" not in serialized
    assert "timeline" not in serialized
    assert document == original


def test_optional_animation_is_observed_but_not_eligible():
    document = load_fixture("optional_animation_network.json")

    analysis = build_analysis_input(document)

    assert legacy_investigations(document) == (
        Investigation.INSPECT_NETWORK,
        Investigation.INSPECT_ANIMATIONS,
    )
    assert analysis.eligible == (Investigation.INSPECT_NETWORK,)
    assert corrected_baseline(analysis) == Investigation.INSPECT_NETWORK


def test_stable_optional_animation_exposes_weak_legacy_baseline():
    document = load_fixture("optional_animation_stable.json")

    analysis = build_analysis_input(document)

    assert legacy_investigations(document) == (Investigation.INSPECT_ANIMATIONS,)
    assert analysis.eligible == (Investigation.INSUFFICIENT_EVIDENCE,)


def test_idle_websocket_is_not_a_blocker():
    analysis = build_analysis_input(load_fixture("idle_websocket.json"))

    assert analysis.eligible == (Investigation.INSUFFICIENT_EVIDENCE,)


def test_contradictory_status_safely_abstains():
    analysis = build_analysis_input(load_fixture("contradictory_status.json"))

    assert analysis.eligible == (Investigation.INSUFFICIENT_EVIDENCE,)
    assert "BLOCKING_SIGNAL_MISMATCH" in analysis.warnings


def test_provider_cannot_choose_an_ineligible_investigation():
    analysis = build_analysis_input(load_fixture("network_only.json"))
    decision = ProviderDecision(
        choice=Investigation.INSPECT_LAYOUT,
        provider="broken",
        confidence=0.99,
        probabilities={},
    )

    with pytest.raises(ProviderError, match="unsupported choice"):
        _validate_decision(decision, analysis)


def test_scripted_provider_is_transparently_labeled():
    analysis = build_analysis_input(load_fixture("network_only.json"))

    decision = run_provider(
        ScriptedProvider(Investigation.INSPECT_NETWORK),
        analysis,
    )

    assert decision.choice == Investigation.INSPECT_NETWORK
    assert decision.provider == "scripted (not TypeSafe)"


def test_typesafe_provider_without_key_fails_before_network(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    analysis = build_analysis_input(load_fixture("network_only.json"))

    with pytest.raises(ProviderError, match="no network request was attempted"):
        run_provider(TypeSafeProvider(), analysis)


def test_typesafe_adapter_accepts_real_response_shape_without_network(monkeypatch):
    captured = {}

    class FakeChoice:
        def __init__(self, **kwargs):
            captured["question"] = kwargs

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def system_one(self, **kwargs):
            captured["request"] = kwargs
            answer = SimpleNamespace(
                choice="INSPECT_NETWORK",
                confidence=0.84,
                probabilities={"INSPECT_NETWORK": 0.84, "INSUFFICIENT_EVIDENCE": 0.16},
            )
            return SimpleNamespace(
                model="jev-test",
                choices={"first_investigation": answer},
            )

    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only")
    monkeypatch.setitem(
        sys.modules,
        "typesafe_sdk",
        SimpleNamespace(Choice=FakeChoice, TypeSafeClient=FakeClient),
    )
    analysis = build_analysis_input(load_fixture("network_only.json"))

    decision = run_provider(TypeSafeProvider(), analysis)

    assert decision.choice == Investigation.INSPECT_NETWORK
    assert decision.provider == "TypeSafe (jev-test)"
    assert decision.confidence == 0.84
    assert decision.provider_called is True
    assert captured["client"] == {"timeout": 10.0}
    assert captured["request"]["state"] == analysis.state


def test_scripted_suite_validates_plumbing_not_model_quality():
    result = evaluate_manifest(
        FIXTURES / "manifest.json",
        provider_mode="scripted",
    )

    assert result["summary"]["cases"] == 10
    assert result["summary"]["provider_acceptable_rate"] == 1.0
    assert result["summary"]["system_acceptable_rate"] == 1.0
    assert result["summary"]["local_short_circuits"] == 4
    assert result["summary"]["note"] == (
        "scripted provider; plumbing demonstration only"
    )
