"""Proof of concept for an opt-in TypeSafe-powered Waitless doctor.

This module deliberately lives under ``examples``. It does not participate in
Waitless's stabilization path and does not add a runtime dependency to the
published package.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple


QUESTION_ID = "first_investigation"
KNOWN_SIGNAL_STATES = {"STABLE", "UNSTABLE", "UNKNOWN"}
KNOWN_STRICTNESS = {"strict", "normal", "relaxed"}
KNOWN_FRAMEWORKS = {"react", "angular", "vue"}


class Investigation(str, Enum):
    INSPECT_NETWORK = "INSPECT_NETWORK"
    INSPECT_DOM_CHURN = "INSPECT_DOM_CHURN"
    INSPECT_ANIMATIONS = "INSPECT_ANIMATIONS"
    INSPECT_LAYOUT = "INSPECT_LAYOUT"
    INSPECT_FRAMEWORK = "INSPECT_FRAMEWORK"
    INSPECT_REALTIME_ACTIVITY = "INSPECT_REALTIME_ACTIVITY"
    INSPECT_IFRAMES = "INSPECT_IFRAMES"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


SIGNAL_TO_INVESTIGATION = {
    "NETWORK_REQUESTS": Investigation.INSPECT_NETWORK,
    "DOM_MUTATIONS": Investigation.INSPECT_DOM_CHURN,
    "CSS_ANIMATIONS": Investigation.INSPECT_ANIMATIONS,
    "CSS_TRANSITIONS": Investigation.INSPECT_ANIMATIONS,
    "LAYOUT_SHIFT": Investigation.INSPECT_LAYOUT,
    "FRAMEWORK_ACTIVITY": Investigation.INSPECT_FRAMEWORK,
    "WEBSOCKET_ACTIVITY": Investigation.INSPECT_REALTIME_ACTIVITY,
    "SSE_ACTIVITY": Investigation.INSPECT_REALTIME_ACTIVITY,
    "IFRAME_READINESS": Investigation.INSPECT_IFRAMES,
}

INVESTIGATION_CRITERIA = {
    Investigation.INSPECT_NETWORK: (
        "Inspect mandatory pending-request activity first. This is an investigation, "
        "not permission to raise the network threshold."
    ),
    Investigation.INSPECT_DOM_CHURN: (
        "Inspect mandatory DOM mutation activity first, including repeated rendering "
        "or content insertion."
    ),
    Investigation.INSPECT_ANIMATIONS: (
        "Inspect animations or transitions that are mandatory under the recorded "
        "configuration."
    ),
    Investigation.INSPECT_LAYOUT: (
        "Inspect mandatory layout movement or a missing layout baseline first."
    ),
    Investigation.INSPECT_FRAMEWORK: (
        "Inspect an enabled framework adapter that reported unsettled rendering."
    ),
    Investigation.INSPECT_REALTIME_ACTIVITY: (
        "Inspect recent mandatory WebSocket or Server-Sent Events activity. Open but "
        "quiet connections alone do not qualify."
    ),
    Investigation.INSPECT_IFRAMES: (
        "Inspect accessible same-origin iframe readiness that blocked stabilization."
    ),
    Investigation.INSUFFICIENT_EVIDENCE: (
        "Choose this when the snapshot is missing, contradictory, already stable, or "
        "does not justify prioritizing one eligible investigation."
    ),
}

RECOMMENDATION_TEMPLATES = {
    Investigation.INSPECT_NETWORK: (
        "Inspect the pending network work and determine whether it is user-critical or "
        "known background traffic before changing any threshold."
    ),
    Investigation.INSPECT_DOM_CHURN: (
        "Inspect repeated DOM updates and identify the component or asynchronous work "
        "that continues after the interaction."
    ),
    Investigation.INSPECT_ANIMATIONS: (
        "Inspect the blocking animation or transition and decide whether the test must "
        "wait for it or the application should disable it in test mode."
    ),
    Investigation.INSPECT_LAYOUT: (
        "Inspect layout shifts, late-loading assets, fonts, and dynamic insertion before "
        "weakening layout checks."
    ),
    Investigation.INSPECT_FRAMEWORK: (
        "Inspect the enabled framework adapter and the application work it reports as "
        "unsettled."
    ),
    Investigation.INSPECT_REALTIME_ACTIVITY: (
        "Inspect recent WebSocket or SSE messages and determine which activity is part "
        "of the user-visible update."
    ),
    Investigation.INSPECT_IFRAMES: (
        "Inspect the same-origin iframe that has not completed loading."
    ),
    Investigation.INSUFFICIENT_EVIDENCE: (
        "Collect another diagnostic snapshot or add explicit operator context; do not "
        "change Waitless configuration from this evidence alone."
    ),
}


class PocError(RuntimeError):
    """Base error for the proof of concept."""


class DiagnosticValidationError(PocError):
    """Raised when a diagnostic or context document has an invalid outer shape."""


class ProviderError(PocError):
    """Raised when a recommendation provider cannot return a valid decision."""


@dataclass(frozen=True)
class AnalysisInput:
    state: Dict[str, Any]
    eligible: Tuple[Investigation, ...]
    warnings: Tuple[str, ...]

    @property
    def provider_options(self) -> Tuple[Investigation, ...]:
        options = list(self.eligible)
        if Investigation.INSUFFICIENT_EVIDENCE not in options:
            options.append(Investigation.INSUFFICIENT_EVIDENCE)
        return tuple(options)


@dataclass(frozen=True)
class ProviderDecision:
    choice: Investigation
    provider: str
    confidence: Optional[float]
    probabilities: Dict[str, float]
    elapsed_ms: float = 0.0
    provider_called: bool = True


class RecommendationProvider(Protocol):
    name: str

    def recommend(self, analysis: AnalysisInput) -> ProviderDecision:
        """Return one choice from ``analysis.provider_options``."""


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def _safe_nonnegative_number(value: Any) -> Optional[Any]:
    numeric = _finite_number(value)
    if numeric is None or numeric < 0:
        return None
    if isinstance(value, int):
        return value
    return numeric


def _sanitize_config(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}

    result: Dict[str, Any] = {}
    numeric_fields = (
        "timeout",
        "dom_settle_time",
        "mutation_rate_threshold",
        "network_idle_threshold",
        "poll_interval",
        "websocket_quiet_time",
    )
    boolean_fields = (
        "animation_detection",
        "layout_stability",
        "track_websocket",
        "track_sse",
        "track_iframes",
    )

    for key in numeric_fields:
        safe = _safe_nonnegative_number(value.get(key))
        if safe is not None:
            result[key] = safe
    for key in boolean_fields:
        if isinstance(value.get(key), bool):
            result[key] = value[key]

    strictness = value.get("strictness")
    if strictness in KNOWN_STRICTNESS:
        result["strictness"] = strictness

    hooks = value.get("framework_hooks")
    if isinstance(hooks, list):
        result["framework_hooks"] = [
            item for item in hooks if item in KNOWN_FRAMEWORKS
        ][:3]
    return result


def _sanitize_signal_value(signal_type: str, value: Any) -> Any:
    if signal_type == "LAYOUT_SHIFT" and isinstance(value, bool):
        return value
    if signal_type == "FRAMEWORK_ACTIVITY" and isinstance(value, Mapping):
        stable = value.get("stable")
        return {"stable": stable} if isinstance(stable, bool) else None
    if signal_type in {"WEBSOCKET_ACTIVITY", "SSE_ACTIVITY"} and isinstance(
        value, Mapping
    ):
        result: Dict[str, Any] = {}
        for key in ("active", "time_since_activity_ms"):
            safe = _safe_nonnegative_number(value.get(key))
            if safe is not None:
                result[key] = safe
        return result or None
    return _safe_nonnegative_number(value)


def _sanitize_threshold(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    return _safe_nonnegative_number(value)


def _sanitize_operator_context(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise DiagnosticValidationError("operator context must be a JSON object")

    unexpected = set(value) - {
        "test_action",
        "application_notes",
        "known_background_activity",
    }
    if unexpected:
        raise DiagnosticValidationError(
            "operator context contains unsupported keys: "
            + ", ".join(sorted(str(key) for key in unexpected))
        )

    result: Dict[str, Any] = {}
    for key, limit in (("test_action", 200), ("application_notes", 500)):
        item = value.get(key)
        if item is not None:
            if not isinstance(item, str):
                raise DiagnosticValidationError(f"operator context {key} must be text")
            result[key] = item[:limit]

    activity = value.get("known_background_activity")
    if activity is not None:
        if not isinstance(activity, list) or not all(
            isinstance(item, str) for item in activity
        ):
            raise DiagnosticValidationError(
                "operator context known_background_activity must be a list of text"
            )
        result["known_background_activity"] = [item[:120] for item in activity[:10]]
    return result


def _sanitize_activity(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, Any] = {}
    for key in (
        "pending_requests",
        "active_animations",
        "mutation_rate",
        "active_websockets",
        "active_sse",
    ):
        safe = _safe_nonnegative_number(value.get(key))
        if safe is not None:
            result[key] = safe
    for key in ("layout_shifting", "recent_mutations"):
        if isinstance(value.get(key), bool):
            result[key] = value[key]
    return result


def _diagnostics_object(document: Any) -> Dict[str, Any]:
    if not isinstance(document, Mapping):
        raise DiagnosticValidationError("diagnostic document must be a JSON object")
    value = document.get("diagnostics", document)
    if not isinstance(value, Mapping):
        raise DiagnosticValidationError("diagnostics must be a JSON object")
    return dict(value)


def build_analysis_input(
    document: Any,
    *,
    operator_context: Any = None,
) -> AnalysisInput:
    """Build the exact allowlisted payload that a provider may receive."""
    diagnostics = _diagnostics_object(document)
    warnings: List[str] = []
    status = diagnostics.get("last_status")
    safe_signals: List[Dict[str, Any]] = []
    computed_blocking: List[str] = []
    declared_blocking: List[str] = []
    is_stable: Optional[bool] = None

    if not isinstance(status, Mapping):
        warnings.append("MISSING_LAST_STATUS")
    else:
        if isinstance(status.get("is_stable"), bool):
            is_stable = status["is_stable"]
        else:
            warnings.append("INVALID_STABILITY_FLAG")

        raw_signals = status.get("signals")
        if not isinstance(raw_signals, list) or not raw_signals:
            warnings.append("MISSING_SIGNALS")
            raw_signals = []

        for raw in raw_signals:
            if not isinstance(raw, Mapping):
                warnings.append("INVALID_SIGNAL")
                continue
            signal_type = raw.get("type")
            state = raw.get("state")
            mandatory = raw.get("mandatory")
            if signal_type not in SIGNAL_TO_INVESTIGATION:
                warnings.append("UNKNOWN_SIGNAL_TYPE")
                continue
            if state not in KNOWN_SIGNAL_STATES or not isinstance(mandatory, bool):
                warnings.append("INVALID_SIGNAL")
                continue

            safe_signal: Dict[str, Any] = {
                "type": signal_type,
                "state": state,
                "mandatory": mandatory,
            }
            safe_value = _sanitize_signal_value(signal_type, raw.get("value"))
            if safe_value is not None:
                safe_signal["value"] = safe_value
            safe_threshold = _sanitize_threshold(raw.get("threshold"))
            if safe_threshold is not None:
                safe_signal["threshold"] = safe_threshold
            safe_signals.append(safe_signal)

            if mandatory and state != "STABLE":
                computed_blocking.append(signal_type)

        raw_blocking = status.get("blocking")
        if not isinstance(raw_blocking, list) or not all(
            isinstance(item, str) for item in raw_blocking
        ):
            warnings.append("INVALID_BLOCKING_LIST")
        else:
            declared_blocking = [
                item for item in raw_blocking if item in SIGNAL_TO_INVESTIGATION
            ]
            if len(declared_blocking) != len(raw_blocking):
                warnings.append("UNKNOWN_BLOCKING_SIGNAL")

    computed_set = set(computed_blocking)
    declared_set = set(declared_blocking)
    if isinstance(status, Mapping) and computed_set != declared_set:
        warnings.append("BLOCKING_SIGNAL_MISMATCH")
    if is_stable is True and computed_set:
        warnings.append("STABLE_WITH_BLOCKERS")
    if is_stable is False and not computed_set and safe_signals:
        warnings.append("UNSTABLE_WITHOUT_BLOCKERS")

    consistency_error = any(
        warning
        in {
            "MISSING_LAST_STATUS",
            "INVALID_STABILITY_FLAG",
            "MISSING_SIGNALS",
            "INVALID_SIGNAL",
            "INVALID_BLOCKING_LIST",
            "UNKNOWN_BLOCKING_SIGNAL",
            "BLOCKING_SIGNAL_MISMATCH",
            "STABLE_WITH_BLOCKERS",
            "UNSTABLE_WITHOUT_BLOCKERS",
        }
        for warning in warnings
    )

    eligible: List[Investigation] = []
    if not consistency_error and is_stable is False:
        for signal in safe_signals:
            signal_type = signal["type"]
            if signal_type not in computed_set:
                continue
            choice = SIGNAL_TO_INVESTIGATION[signal_type]
            if choice not in eligible:
                eligible.append(choice)

    if not eligible:
        eligible = [Investigation.INSUFFICIENT_EVIDENCE]

    schema_version = diagnostics.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        schema_version = None

    state: Dict[str, Any] = {
        "diagnostic_schema_version": schema_version,
        "config": _sanitize_config(diagnostics.get("config")),
        "status": {
            "is_stable": is_stable,
            "signals": safe_signals,
            "blocking": sorted(computed_set),
        },
        "observed_activity": _sanitize_activity(diagnostics.get("blocking_factors")),
        "eligible_investigations": [item.value for item in eligible],
        "consistency_warnings": sorted(set(warnings)),
    }
    safe_context = _sanitize_operator_context(operator_context)
    if safe_context:
        state["operator_context"] = safe_context

    return AnalysisInput(
        state=state,
        eligible=tuple(eligible),
        warnings=tuple(sorted(set(warnings))),
    )


def build_question_spec(analysis: AnalysisInput) -> Dict[str, Any]:
    return {
        "type": "choice",
        "instructions": {
            "question": (
                "Which eligible investigation should the developer perform first for "
                "this Waitless diagnostic snapshot?"
            ),
            "inspect": [
                "`status.signals`",
                "`status.blocking`",
                "`observed_activity`",
                "`operator_context` when present",
            ],
            "constraints": [
                "Choose only from the supplied criteria.",
                "Observed activity is not necessarily blocking activity.",
                "Do not invent page facts or configuration values.",
                "Choose INSUFFICIENT_EVIDENCE when the snapshot does not justify a priority.",
            ],
        },
        "criteria": {
            option.value: INVESTIGATION_CRITERIA[option]
            for option in analysis.provider_options
        },
    }


def legacy_investigations(document: Any) -> Tuple[Investigation, ...]:
    """Mirror the ordering of the current rule-based doctor suggestions."""
    diagnostics = _diagnostics_object(document)
    blocking = diagnostics.get("blocking_factors")
    if not isinstance(blocking, Mapping):
        return ()

    result: List[Investigation] = []
    if (_safe_nonnegative_number(blocking.get("pending_requests")) or 0) > 0:
        result.append(Investigation.INSPECT_NETWORK)
    if (_safe_nonnegative_number(blocking.get("active_animations")) or 0) > 0:
        result.append(Investigation.INSPECT_ANIMATIONS)
    if blocking.get("layout_shifting") is True:
        result.append(Investigation.INSPECT_LAYOUT)
    return tuple(result)


def corrected_baseline(analysis: AnalysisInput) -> Investigation:
    return analysis.eligible[0]


def _validate_decision(
    decision: ProviderDecision,
    analysis: AnalysisInput,
) -> ProviderDecision:
    if decision.choice not in analysis.provider_options:
        allowed = ", ".join(item.value for item in analysis.provider_options)
        raise ProviderError(
            f"provider returned unsupported choice {decision.choice.value}; "
            f"allowed choices: {allowed}"
        )
    if decision.confidence is not None:
        confidence = _finite_number(decision.confidence)
        if confidence is None or not 0 <= confidence <= 1:
            raise ProviderError("provider confidence must be between 0 and 1")
    for key, value in decision.probabilities.items():
        if key not in {item.value for item in analysis.provider_options}:
            raise ProviderError(
                f"provider returned probability for unsupported choice {key}"
            )
        probability = _finite_number(value)
        if probability is None or not 0 <= probability <= 1:
            raise ProviderError("provider probabilities must be between 0 and 1")
    return decision


class ScriptedProvider:
    """Transparent test double for plumbing demonstrations only."""

    name = "scripted (not TypeSafe)"

    def __init__(self, choice: Investigation):
        self.choice = choice

    def recommend(self, analysis: AnalysisInput) -> ProviderDecision:
        return ProviderDecision(
            choice=self.choice,
            provider=self.name,
            confidence=None,
            probabilities={},
        )


class TypeSafeProvider:
    """Lazy adapter around the optional TypeSafe Python SDK."""

    def __init__(self, *, model: Optional[str] = None):
        self.model = model
        self.name = f"TypeSafe ({model or 'SDK default'})"

    def recommend(self, analysis: AnalysisInput) -> ProviderDecision:
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise ProviderError(
                "TYPESAFE_API_KEY is not set; no network request was attempted"
            )
        try:
            from typesafe_sdk import Choice, TypeSafeClient
        except ImportError as exc:
            raise ProviderError(
                "typesafe-sdk is not installed; use a separate Python 3.10+ demo "
                "environment and install typesafe-sdk==0.6.0"
            ) from exc

        question = build_question_spec(analysis)
        kwargs: Dict[str, Any] = {
            "state": analysis.state,
            "questions": {
                QUESTION_ID: Choice(
                    instructions=question["instructions"],
                    criteria=question["criteria"],
                )
            },
        }
        if self.model:
            kwargs["model"] = self.model

        with TypeSafeClient(timeout=10.0) as client:
            response = client.system_one(**kwargs)

        if hasattr(response, "choices"):
            answer = response.choices[QUESTION_ID]
        elif hasattr(response, "answers"):
            answer = response.answers[QUESTION_ID]
        else:
            raise ProviderError("TypeSafe response did not contain typed answers")

        try:
            choice = Investigation(str(answer.choice))
            confidence = float(answer.confidence)
            probabilities = {
                str(key): float(value)
                for key, value in dict(answer.probabilities).items()
            }
        except (AttributeError, TypeError, ValueError) as exc:
            raise ProviderError("TypeSafe returned an invalid Choice answer") from exc

        return ProviderDecision(
            choice=choice,
            provider=f"TypeSafe ({getattr(response, 'model', self.model or 'unknown')})",
            confidence=confidence,
            probabilities=probabilities,
        )


def run_provider(
    provider: RecommendationProvider,
    analysis: AnalysisInput,
) -> ProviderDecision:
    if analysis.provider_options == (Investigation.INSUFFICIENT_EVIDENCE,):
        return ProviderDecision(
            choice=Investigation.INSUFFICIENT_EVIDENCE,
            provider="local safety short-circuit",
            confidence=None,
            probabilities={},
            elapsed_ms=0.0,
            provider_called=False,
        )

    started = time.monotonic()
    decision = provider.recommend(analysis)
    elapsed_ms = (time.monotonic() - started) * 1000
    timed = ProviderDecision(
        choice=decision.choice,
        provider=decision.provider,
        confidence=decision.confidence,
        probabilities=dict(decision.probabilities),
        elapsed_ms=elapsed_ms,
        provider_called=decision.provider_called,
    )
    return _validate_decision(timed, analysis)


def result_document(
    document: Any,
    analysis: AnalysisInput,
    *,
    decision: Optional[ProviderDecision],
    include_payload: bool,
) -> Dict[str, Any]:
    legacy = legacy_investigations(document)
    baseline = corrected_baseline(analysis)
    result: Dict[str, Any] = {
        "existing_heuristics": [item.value for item in legacy],
        "corrected_signal_baseline": baseline.value,
        "eligible_investigations": [item.value for item in analysis.provider_options],
        "consistency_warnings": list(analysis.warnings),
        "provider_decision": None,
    }
    if decision is not None:
        result["provider_decision"] = {
            "choice": decision.choice.value,
            "recommendation": RECOMMENDATION_TEMPLATES[decision.choice],
            "provider": decision.provider,
            "confidence": decision.confidence,
            "probabilities": dict(decision.probabilities),
            "elapsed_ms": round(decision.elapsed_ms, 3),
            "provider_called": decision.provider_called,
        }
    if include_payload:
        result["outbound_preview"] = {
            "state": copy.deepcopy(analysis.state),
            "questions": {QUESTION_ID: build_question_spec(analysis)},
        }
    return result


def render_text(result: Mapping[str, Any]) -> str:
    lines = ["WAITLESS TYPESAFE DOCTOR POC", ""]
    legacy = result.get("existing_heuristics") or []
    lines.append(
        "Existing heuristics: "
        + (", ".join(legacy) if legacy else "no targeted advice")
    )
    lines.append(
        "Corrected signal baseline: " + str(result["corrected_signal_baseline"])
    )
    lines.append("Eligible choices: " + ", ".join(result["eligible_investigations"]))
    warnings = result.get("consistency_warnings") or []
    if warnings:
        lines.append("Safety warnings: " + ", ".join(warnings))

    decision = result.get("provider_decision")
    if decision:
        lines.extend(
            [
                "",
                f"Provider: {decision['provider']}",
                f"Choice: {decision['choice']}",
                f"Confidence: {decision['confidence']}",
                f"Elapsed: {decision['elapsed_ms']} ms",
                f"Recommendation: {decision['recommendation']}",
            ]
        )
    else:
        lines.extend(["", "Provider: not called (dry run)"])

    if "outbound_preview" in result:
        lines.extend(
            [
                "",
                "Outbound payload preview:",
                json.dumps(result["outbound_preview"], indent=2, sort_keys=True),
            ]
        )
    return "\n".join(lines)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DiagnosticValidationError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DiagnosticValidationError(f"invalid JSON in {path}: {exc}") from exc


def parse_investigation(value: str) -> Investigation:
    try:
        return Investigation(value)
    except ValueError as exc:
        choices = ", ".join(item.value for item in Investigation)
        raise argparse.ArgumentTypeError(f"expected one of: {choices}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare Waitless doctor heuristics with an optional TypeSafe advisor."
    )
    parser.add_argument(
        "diagnostics", type=Path, help="saved Waitless diagnostics JSON"
    )
    parser.add_argument(
        "--provider",
        choices=("dry-run", "scripted", "typesafe"),
        default="dry-run",
        help="dry-run previews the payload; scripted only demonstrates plumbing",
    )
    parser.add_argument(
        "--scripted-choice",
        type=parse_investigation,
        help="required with --provider scripted",
    )
    parser.add_argument(
        "--context-file",
        type=Path,
        help="optional explicitly-authored, allowlisted operator context JSON",
    )
    parser.add_argument("--model", help="optional TypeSafe model override")
    parser.add_argument(
        "--show-payload",
        action="store_true",
        help="show the exact allowlisted state and question",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = load_json(args.diagnostics)
        context = load_json(args.context_file) if args.context_file else None
        analysis = build_analysis_input(document, operator_context=context)

        decision: Optional[ProviderDecision] = None
        if args.provider == "scripted":
            if args.scripted_choice is None:
                raise ProviderError(
                    "--scripted-choice is required for scripted provider"
                )
            decision = run_provider(ScriptedProvider(args.scripted_choice), analysis)
        elif args.provider == "typesafe":
            decision = run_provider(TypeSafeProvider(model=args.model), analysis)

        include_payload = args.show_payload or args.provider == "dry-run"
        result = result_document(
            document,
            analysis,
            decision=decision,
            include_payload=include_payload,
        )
    except PocError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
