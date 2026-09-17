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

The current `typesafe-sdk==0.6.0` requires Python 3.10+, while Waitless supports Python
3.9+. Keep the SDK in a separate demo environment so the published package remains
unchanged:

```bash
python3.10 -m venv .venv-typesafe
.venv-typesafe/bin/pip install -e . typesafe-sdk==0.6.0
export TYPESAFE_API_KEY='...'
```

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
