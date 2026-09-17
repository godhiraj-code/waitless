# TypeSafe smart doctor proof of concept

This experiment tests one narrow question: can TypeSafe prioritize the first useful
investigation after a Waitless stabilization timeout better than deterministic rules?

It does **not** change Waitless's stabilization engine, automatically alter configuration,
or add TypeSafe to the package's runtime dependencies. The experiment compares:

1. the current doctor's observed-activity heuristics;
2. a corrected baseline using `last_status.blocking`; and
3. an optional TypeSafe `Choice` over only the eligible investigations.

The distinction matters because observed activity is not always blocking. For example,
animations are optional outside strict mode, and an open but quiet WebSocket is stable.

## Current status

The POC was exercised against the live TypeSafe service on September 17, 2026 using
`typesafe-sdk==0.6.0` and the service-selected `jev-1.13.0` model.

| Measurement | Result |
|-------------|-------:|
| Labeled synthetic cases | 10 |
| Existing heuristic acceptable | 50% |
| Corrected deterministic baseline acceptable | 90% |
| TypeSafe provider acceptable | 100% |
| Complete system acceptable | 100% |
| Provider errors | 0 |
| Local safety short-circuits | 4 |
| Mean provider latency | 820 ms |
| p95 provider latency | 996 ms |

Four incomplete, contradictory, or already-stable cases were resolved locally without
calling TypeSafe. TypeSafe handled the other six. It disagreed with the corrected
baseline once: for `mixed_required_network`, the baseline selected DOM churn by fixed
signal order, while TypeSafe used the explicitly authored operator context and selected
the labeled network investigation. Three additional repetitions made the same selection,
with confidence from `0.69` to `0.72` and latency from `899` to `950` ms.

This is evidence to continue evaluating TypeSafe as an optional post-timeout advisor,
not evidence to put it in the stabilization polling path or ship it as a production
dependency. The suite is small, synthetic, and partially designed around known edge
cases. A production decision requires independently labeled diagnostics from real
applications.

## Safety boundary

The TypeSafe provider receives an allowlisted payload containing:

- numeric and boolean configuration;
- enumerated signal type, state, and mandatory status;
- numeric signal values and thresholds;
- aggregate activity counts;
- optional operator-authored context from three documented fields.

It excludes URLs, request details, timeline messages, signal descriptions, page content,
DOM, screenshots, and arbitrary nested diagnostic data. Always inspect `--show-payload`
before a live call and never place secrets in the optional context file.

## Run without TypeSafe

Dry-run mode makes no network request and displays the exact outbound payload:

```bash
python examples/typesafe_doctor/poc.py \
  examples/typesafe_doctor/fixtures/optional_animation_network.json \
  --provider dry-run
```

Scripted mode proves the plumbing only. It must not be reported as a TypeSafe result:

```bash
python examples/typesafe_doctor/poc.py \
  examples/typesafe_doctor/fixtures/network_only.json \
  --provider scripted \
  --scripted-choice INSPECT_NETWORK
```

Evaluate every fixture against both deterministic baselines:

```bash
python examples/typesafe_doctor/evaluate.py --provider scripted
```

## Run live with TypeSafe

The POC was validated with `typesafe-sdk==0.6.0`, which requires Python 3.10+, while
Waitless supports Python 3.9+. Keep the SDK in a separate demo environment so the
published package remains unchanged:

```bash
python3 --version  # Must be 3.10 or newer for typesafe-sdk==0.6.0
python3 -m venv .venv-typesafe
.venv-typesafe/bin/pip install -e . typesafe-sdk==0.6.0
read -rsp "TypeSafe API key: " TYPESAFE_API_KEY
echo
export TYPESAFE_API_KEY
```

The live provider sends the allowlisted payload to the external TypeSafe service. Review
it with `--show-payload` first. Do not put the key in the repository, shell history,
diagnostic JSON, or operator context.

Run one reviewed fixture first:

```bash
.venv-typesafe/bin/python examples/typesafe_doctor/poc.py \
  examples/typesafe_doctor/fixtures/optional_animation_network.json \
  --provider typesafe \
  --show-payload
```

The mixed-signal fixture demonstrates the part deterministic signal ordering cannot
resolve by itself. Its context file is explicitly authored and included in the outbound
preview:

```bash
.venv-typesafe/bin/python examples/typesafe_doctor/poc.py \
  examples/typesafe_doctor/fixtures/mixed_required_network.json \
  --provider typesafe \
  --context-file examples/typesafe_doctor/operator_context.example.json \
  --show-payload
```

Then run the labeled suite:

```bash
.venv-typesafe/bin/python examples/typesafe_doctor/evaluate.py --provider typesafe
unset TYPESAFE_API_KEY
```

If `TYPESAFE_API_KEY` is missing, the live provider fails before importing the SDK or
attempting a request.

## What would count as useful?

The live provider should be judged on:

- acceptable first-investigation rate;
- unsupported recommendations (must remain zero);
- abstention on missing or contradictory evidence;
- disagreement with the corrected deterministic baseline;
- repeated-answer consistency;
- mean and p95 latency.

The small included suite validates mechanics and safety, not model quality. A credible
decision needs representative, manually labeled diagnostics from real applications. If
TypeSafe merely reproduces the corrected baseline, that is evidence against adding the
integration.

Current references: [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python),
[Choice primitive](https://docs.typesafe.ai/primitives/choice), and
[confidence](https://docs.typesafe.ai/confidence).
