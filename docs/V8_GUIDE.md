# Healthcare Quality Lab V8 — operator and learning guide

## What you are installing

One standalone Python application with Flask, SQLite, pytest and Playwright. All members, plans, claims, payments and policies are synthetic. Local Ollama is optional; deterministic tests, coverage packs, review routing and evidence inspection work without it. No paid-provider fallback or model download is part of these commands.

## Start from a clean checkout

Install Python 3.11–3.13, clone this repository into a new directory, then run:

```sh
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.doctor --ollama
.venv/bin/python -m tools.launch_demo --state-dir .local/v8-first-demo --port 8899
```

On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe`. Open http://127.0.0.1:8899/#workbench. Existing nonempty demo state is rejected rather than reset. The launcher bootstraps runtime dependencies, not a model. The browser switch is only needed for browser testing. `doctor` is read-only; optional Ollama availability does not fail an otherwise usable deterministic runtime.

If dependency installation fails, preserve the output and check the Python version and network/proxy setup. If a port is occupied, select another unused port. If demo state exists, choose a fresh name. Do not delete an existing project or SQLite file to solve a setup error. For missing browser binaries run `.venv/bin/python -m playwright install chromium`; browser availability is separate from the runtime doctor's checks.

## A ten-minute engineering walkthrough

1. Open V8 quality workbench and inspect eight coverage packs. Medicare Advantage and Part C refer to the same pack.
2. Select Medicare Part D and create an unapproved pack proposal. This action uses an authored scenario and independently calculated expectations, with zero model calls.
3. Explain selected evidence. The bounded evidence assistant returns saved facts, citations, issues and uncertainty. These are deterministic findings, not generated model prose.
4. Assign an owner and routing decision. A ready-for-review decision is not approval.
5. Open separate review and HTTP execution. Inspect every money, ledger, revision, event-count and accumulator assertion. Approve explicitly with an accurate inspection note, then execute against fresh synthetic HTTP state.
6. Optionally ask an installed local model for a new plan. Poll its saved design. Quality-gated export refuses missing financial readbacks and stale source. Calculator-authored expectations are not AI financial reasoning.
7. Run a calculator experiment first, then explicitly select raw local AI if desired. Polling and page loads make no inference requests. Raw failures, provider errors, repeated instability and cancellation are retained.
8. Inspect the ten version reports and the archived V7 evidence. Historical receipts are not current verification.

## Reproduce engineering checks

```sh
.venv/bin/python -m tools.verify
.venv/bin/python -m pytest tests/e2e --browser chromium --browser firefox --browser webkit -q
.venv/bin/python -m tools.v8_rehearsal --output artifacts/v8.0/my-cross-system-run.json
.venv/bin/python -m tools.resilience --output artifacts/v8.0/my-resilience.json
.venv/bin/python -m tools.dependency_audit --output artifacts/v8.0/my-dependency-audit.json
```

Install other browser binaries explicitly before the three-browser sweep. The vulnerability lookup sends installed public package names and versions to OSV without credentials; an unavailable lookup returns unknown, not clean. Rehearsal and evidence commands refuse existing output paths. These are bounded controls, not production load or security certification.

## Measure actual local AI

```sh
.venv/bin/python -m tools.v8_evaluate --models qwen2.5-coder:3b qwen3.5:27b --prompts baseline-v67 focused-v68 --tasks EV8-13 EV8-16 --repeats 2 --mode ai_expectations --state .local/my-v8-evaluation.sqlite --output artifacts/v8.0/my-raw-model-comparison.json --dry-run
```

Inspect the 16-request budget before removing `--dry-run`. Each raw row makes exactly one model request, with no correction, approval or execution. Use `--mode calculator_control` for zero-inference controls. The 31-scenario cohort separates development and reserved scenario families; selection, source, cohort, prompt hashes, installed model digests and settings are retained. A real request consumes local exposure. Repeated trials are correlated, not independent population estimates. Never tune prompts against reserved results and continue calling them unseen.

## Learn several AI tools without confusing their roles

Codex performed the implementation and engineering checks. Ollama executes actual local inference. ChatGPT, Copilot and Claude Code are optional learning exercises here; they were not silently invoked, purchased or credited as executed tools.

- ChatGPT exercise: provide one synthetic pack definition and ask for risks and missing scenarios. Compare the suggestions with `scenario_quality.inspect` and requirement links. Do not supply real patient information.
- Copilot exercise: write an incomplete test for idempotent payment, ask for a completion, then deliberately introduce a duplicate debit. A useful test must fail on the defect. Keep generated code under ordinary code review; the application never executes generated Python.
- Claude Code exercise: ask for a read-only assessment of `system_adapters.py` and its tests. Require file references and compare the suggestions with actual HTTP receipts.
- Ollama exercise: generate one input plan, inspect missing readbacks, then export only after the separate quality gate. Compare with raw model-authored expectations on the same frozen input. Report who authored the expected values.

## Team mode and safety boundaries

The default loopback runtime uses teaching attestations. Shared mode requires configured password hashes and an external session secret through the existing identity tooling. Analyst/reviewer/admin roles can propose and route; only reviewer/admin roles can approve. Auditors read evidence. CSRF is required for shared-mode writes. Authenticated usernames, rather than a supplied label, identify the reviewing/routing actor. Do not expose local mode to the internet. This project does not provide enterprise identity, a clinical system, payer connectivity or a HIPAA certification.

## Package and compare evidence

```sh
.venv/bin/python -m tools.evidence_bundle build --output artifacts/v8.0/my-evidence.zip artifacts/v8.0/my-cross-system-run.json docs/V8.0_REPORT.md
.venv/bin/python -m tools.evidence_bundle verify artifacts/v8.0/my-evidence.zip
.venv/bin/python -m tools.evidence_bundle compare artifacts/v8.0/older.zip artifacts/v8.0/my-evidence.zip
```

Only explicitly selected public docs/artifacts are accepted; local state and credentials are excluded. A manifest covers every member. Checksums detect changes; they are not a publisher signature. A file comparison is not an equal-budget model-performance comparison.

## Reproduce the actual UI demonstration

For a fast diagnostic recording in disposable state:

```sh
.venv/bin/python -m tools.record_workbench --output artifacts/v8.0/my-fast-recording
```

For the readable presentation variant used in this delivery:

```sh
.venv/bin/python artifacts/v8.0/paced-driver.py --output artifacts/v8.0/my-paced-recording
```

The published driver is a copy of the trusted recording tool with explicit five-second reading holds and a final viewport reset. It records actual browser actions, screenshots, Playwright trace and captions; the holds are not application latency. Neither command invokes a model. Existing output directories are refused. The reviewer label accurately identifies scripted Codex engineering inspection, not a human reviewer.

The running delivery demo contains separately labeled copies of the actual comparison and AI plan, with no inference on replay and no copied approval. See artifacts/v8.0/demo-replay.json for those instance-specific IDs; fresh clones can inspect the public JSON receipts or run their own explicit experiments.
