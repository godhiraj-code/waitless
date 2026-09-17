"""Evaluate the TypeSafe doctor POC against labeled diagnostic fixtures."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    from .poc import (
        Investigation,
        PocError,
        ScriptedProvider,
        TypeSafeProvider,
        build_analysis_input,
        corrected_baseline,
        legacy_investigations,
        load_json,
        run_provider,
    )
except ImportError:  # Allow direct execution from the repository checkout.
    from poc import (  # type: ignore
        Investigation,
        PocError,
        ScriptedProvider,
        TypeSafeProvider,
        build_analysis_input,
        corrected_baseline,
        legacy_investigations,
        load_json,
        run_provider,
    )


HERE = Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "fixtures" / "manifest.json"


def _percentile_95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return ordered[index]


def evaluate_manifest(
    manifest_path: Path,
    *,
    provider_mode: str,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("cases"), list):
        raise PocError("fixture manifest must contain a cases list")

    rows: List[Dict[str, Any]] = []
    for case in manifest["cases"]:
        if not isinstance(case, dict):
            raise PocError("each fixture case must be an object")
        case_id = str(case.get("id", "unnamed"))
        fixture_path = manifest_path.parent / str(case.get("file", ""))
        document = load_json(fixture_path)
        analysis = build_analysis_input(
            document,
            operator_context=case.get("operator_context"),
        )
        acceptable = {Investigation(value) for value in case.get("acceptable", [])}
        if not acceptable:
            raise PocError(f"fixture {case_id} has no acceptable choices")

        baseline = corrected_baseline(analysis)
        legacy = legacy_investigations(document)
        legacy_first = legacy[0] if legacy else Investigation.INSUFFICIENT_EVIDENCE
        decision = None
        error = None
        if provider_mode == "scripted":
            scripted = Investigation(case["scripted_choice"])
            provider = ScriptedProvider(scripted)
            decision = run_provider(provider, analysis)
        elif provider_mode == "typesafe":
            try:
                decision = run_provider(TypeSafeProvider(model=model), analysis)
            except PocError as exc:
                error = str(exc)

        rows.append(
            {
                "id": case_id,
                "acceptable": sorted(item.value for item in acceptable),
                "existing_heuristics": [item.value for item in legacy],
                "legacy_first": legacy_first.value,
                "legacy_acceptable": legacy_first in acceptable,
                "corrected_baseline": baseline.value,
                "baseline_acceptable": baseline in acceptable,
                "provider_choice": decision.choice.value if decision else None,
                "provider_acceptable": decision.choice in acceptable
                if decision
                else None,
                "provider": decision.provider if decision else None,
                "provider_called": decision.provider_called if decision else None,
                "elapsed_ms": decision.elapsed_ms if decision else None,
                "disagrees_with_baseline": (
                    decision.choice != baseline if decision else None
                ),
                "abstained": (
                    decision.choice == Investigation.INSUFFICIENT_EVIDENCE
                    if decision
                    else None
                ),
                "warnings": list(analysis.warnings),
                "error": error,
            }
        )

    system_rows = [row for row in rows if row["provider_choice"] is not None]
    provider_rows = [row for row in rows if row["provider_called"] is True]
    elapsed = [float(row["elapsed_ms"]) for row in provider_rows]
    summary = {
        "mode": provider_mode,
        "note": (
            "scripted provider; plumbing demonstration only"
            if provider_mode == "scripted"
            else (
                "live TypeSafe evaluation"
                if provider_mode == "typesafe"
                else "no provider called; deterministic baselines only"
            )
        ),
        "cases": len(rows),
        "legacy_acceptable_rate": (
            sum(bool(row["legacy_acceptable"]) for row in rows) / len(rows)
            if rows
            else None
        ),
        "baseline_acceptable_rate": (
            sum(bool(row["baseline_acceptable"]) for row in rows) / len(rows)
            if rows
            else None
        ),
        "provider_acceptable_rate": (
            sum(bool(row["provider_acceptable"]) for row in provider_rows)
            / len(provider_rows)
            if provider_rows
            else None
        ),
        "system_acceptable_rate": (
            sum(bool(row["provider_acceptable"]) for row in system_rows)
            / len(system_rows)
            if system_rows
            else None
        ),
        "provider_abstention_rate": (
            sum(bool(row["abstained"]) for row in provider_rows) / len(provider_rows)
            if provider_rows
            else None
        ),
        "provider_disagreement_rate": (
            sum(bool(row["disagrees_with_baseline"]) for row in provider_rows)
            / len(provider_rows)
            if provider_rows
            else None
        ),
        "provider_errors": sum(row["error"] is not None for row in rows),
        "local_short_circuits": sum(
            row["provider_choice"] is not None and row["provider_called"] is False
            for row in rows
        ),
        "mean_elapsed_ms": sum(elapsed) / len(elapsed) if elapsed else None,
        "p95_elapsed_ms": _percentile_95(elapsed),
    }
    return {"summary": summary, "cases": rows}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate the TypeSafe doctor POC against labeled fixtures."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--provider",
        choices=("dry-run", "scripted", "typesafe"),
        default="dry-run",
    )
    parser.add_argument("--model", help="optional TypeSafe model override")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = evaluate_manifest(
            args.manifest,
            provider_mode=args.provider,
            model=args.model,
        )
    except (PocError, KeyError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        summary = result["summary"]
        print("WAITLESS TYPESAFE DOCTOR EVALUATION")
        print(f"Mode: {summary['mode']}")
        print(f"Note: {summary['note']}")
        print(f"Cases: {summary['cases']}")
        print(f"Existing heuristic acceptable: {summary['legacy_acceptable_rate']}")
        print(f"Corrected baseline acceptable: {summary['baseline_acceptable_rate']}")
        print(f"Provider acceptable: {summary['provider_acceptable_rate']}")
        print(f"Whole system acceptable: {summary['system_acceptable_rate']}")
        print(f"Provider abstention: {summary['provider_abstention_rate']}")
        print(f"Provider disagreement: {summary['provider_disagreement_rate']}")
        print(f"Provider errors: {summary['provider_errors']}")
        print(f"Local safety short-circuits: {summary['local_short_circuits']}")
        print(
            f"Mean / p95 latency: {summary['mean_elapsed_ms']} / {summary['p95_elapsed_ms']} ms"
        )
        print("")
        for row in result["cases"]:
            print(
                f"{row['id']}: baseline={row['corrected_baseline']} "
                f"provider={row['provider_choice']} acceptable={row['provider_acceptable']}"
            )
            if row["error"]:
                print(f"  error: {row['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
