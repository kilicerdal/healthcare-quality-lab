# Healthcare Quality Lab — V5.7

A standalone quality engineering showcase built with **Python, pytest, Playwright and local Ollama**. Learn to define contracts, test stateful claims, review AI-created cases, measure test quality and release verified source packages.

**Synthetic teaching data only.** The plan amounts, demo identities and payments are invented. Medicare Advantage is Part C. This lab is not a real payer system.

## V5.1 corrections

Cached bytecode is rejected from staged releases; abandoned Studio operations recover using persisted leases; exact rule IDs return only explicitly selected sources. Interrupted generation retries create a new unapproved child. Interrupted execution requires fresh review. Stop V5 workers before using the same stores with V5.1. The original V5 release remains preserved.

## V5.2 assertion completeness

Outcome-specific local generation requests payout, payment and history observations. Per-step checklists block incomplete approval, execution and new pytest export. Older approvals need fresh policy review. The live comparison improved required-field presence from 41/51 to 51/51, but full-reference passes were 2/8 baseline versus 1/8 V5.2; numeric correctness still needs independent review. See the detailed report.

## V5.3 independent expectations and AI correction

A separate standard-library reference model calculates payout, payment and history without calling the application. Mismatched expectations block approval, execution and export. Explicit Ollama correction creates a separate draft with frozen scenario fields and requires fresh review. The eight-task live demonstration improved correct answers from 3/8 to 6/8 after one correction; two wrong drafts remained blocked. Read the [detailed V5.3 report](docs/V5.3_REPORT.md).

## V5.4 bounded correction and confirmed reference assistance

Focused local Ollama correction repaired both retained V5.3 failures: 10,001 cents now expects payout 1, and 286,450 expects 200,000. Both repaired tests and exported pytest wrappers pass. Six separately authored new tasks improved from 4/6 correct to 6/6 after correction. AI requests are limited to two per correction history; a previewed, explicitly confirmed reference fallback creates a distinctly labeled draft requiring fresh review. Read the [detailed V5.4 report](docs/V5.4_REPORT.md).

## V5.5 test coverage and observed defect detection

The [coverage dashboard](http://127.0.0.1:8895/#test-coverage) maps 13 written rules, an explicit 32-case authored catalog and current Studio proposals. Eleven scenario predicates identify gaps; duplicate checks distinguish equivalent inputs, assertion differences and conflicts. Local Ollama suggests grounded gaps and explicitly generates unapproved proposals. Reviewed cases must pass a healthy baseline before scoring against twelve controlled fault profiles. Errors never earn detection credit.

The live demonstration generated two correct gap cases with three actual model requests, closing two of four defined gaps. That two-case suite detected only 2/12 applicable seeds, with ten survivors retained. This is distinct from the authored framework benchmark's 12/12 detections. Read the [detailed V5.5 report](docs/V5.5_REPORT.md).

## V5.6 survivor-targeted tests and guided showcase

The reviewed primary suite improved from 2/12 to 12/12 known fault seeds, with ten new detections and zero regressions. Alternate development inputs also reach 12/12. Each final suite contains one AI-authored workflow and one reference-assisted evaluator; raw errors and corrections remain visible. The polished dashboard shows score/source context, plain-language metrics, survivor plans and a fair comparison matrix. Read the [detailed V5.6 report](docs/V5.6_REPORT.md) and [guided demo](docs/V5.6_DEMO.md).

## V5.7 focused AI generation and complete defined gap map

The installed local `qwen3.5:27b` generated 20/20 correct first-attempt evaluator assertions/calculations on the frozen development cohort, with zero AI corrections and zero reference-assisted replacements. One-request generation retrieves one plan and relevant rules; visible structured calculations are independently checked. Reviewed sources assemble into a fresh unapproved suite by copying exact input/expectation snapshots. The core AI-derived suite detects 12/12 known seeds without a reference-assisted evaluator. Zero-amount rejection and paid-payment replay with unchanged readback close the last two of eleven defined scenario gaps.

The 27B runtime uses explicit prompt JSON with validation; smaller models use constrained output. Failed small-model pilots and runtime-compatibility attempts are preserved separately. This is a development demonstration, not blind-holdout performance or exhaustive defect coverage. Read the [detailed V5.7 report](docs/V5.7_REPORT.md) and [guided demo](docs/V5.7_DEMO.md).

## Start here

```sh
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.serve --port 8895
```

Open [the guided showcase](http://127.0.0.1:8895/#showcase). In VS Code select `.venv/bin/python` and **Run and Debug → V5: start Healthcare Quality Lab**. Bootstrap uses only this project's `.venv` and `.browsers`; it does not install Ollama or download models. On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Read the [V5.7 focused-generation report](docs/V5.7_REPORT.md), [eight-minute demo](docs/V5_DEMO.md), [release operations guide](docs/OPERATIONS.md) and [final architecture narrative](docs/ARCHITECTURE.md). Earlier version reports remain at `/reports/v1` through `/reports/v4`.

## What the five versions deliver

| Version | Concrete outcome |
| --- | --- |
| V1 | Eight synthetic plan configurations, written rules, evaluator, rule trace, unit/API/browser tests |
| V2 | Owned persisted claims, duplicate protection, approval/payment order, simulated ledger, atomic history |
| V3 | Actual local Ollama proposals, validation, edits, explicit review, hash-bound approval, disposable execution |
| V4 | Eight authored evaluation tasks, frozen prompt comparisons, rule retrieval, cited failure hypotheses |
| V5 | Guided showcase, Waitress serving, readiness/request tracing, checked packaging, local activation/rollback and GitHub Actions |

**V5.7 local verification:** 622 tests passed (510 unit, 70 API, 42 Chromium), zero failures/skips. [GitHub Actions passed](https://github.com/kilicerdal/healthcare-quality-lab/actions/runs/43314919548); downloaded evidence matches the final local source fingerprint.

## Test the application

```sh
.venv/bin/python -m tools.verify
.venv/bin/python -m pytest -m smoke -v
.venv/bin/python -m pytest -m sanity -v
.venv/bin/python -m pytest -m ai -v
.venv/bin/python -m pytest -m e2e --headed --slowmo 350
```

The deterministic suite uses clearly labeled offline provider doubles. Real V4 model measurements are preserved separately: 16 proposals plus one explanation. Both compared prompts omitted important assertions; the longer prompt did not outperform the baseline. Read the report rather than treating a generated case count as evidence of quality.

## Create and run local AI cases

1. Start your existing Ollama service with an installed allowed model (`qwen3.5:27b`, `qwen2.5-coder:3b` or `qwen2.5:3b`). Check it explicitly in AI Test Studio.
2. Provide a synthetic requirement, select 1–6 written contracts and request 1–4 cases. Generation creates new declarative case proposals, not a prerecorded catalog selection.
3. Inspect inputs, expectations, source IDs, completeness and independent reference checks. Use explicit Ollama correction (at most two attempts per history), inspect and confirm reference replacements, or edit expectations with a reviewer label and note. Every correction remains unapproved until fresh review; wrong values stay blocked.
4. Select valid cases, attest that you checked their expectations, and save the review. Editing clears approval; stale fingerprints and mismatched hashes block execution.
5. Execute the approved snapshot. Each case gets a fresh disposable SQLite database. Interactive claims are not used. Export evidence JSON or the fixed trusted pytest wrapper.

Reviewer labels are local attestations, not authenticated human identity. The model has no shell, database, file, browser or arbitrary network tools. Cases allow only evaluate/submit/transition/read, at most four cases with eight steps each. They exercise Python services through HTTP-equivalent observations; authored Playwright tests exercise the real UI/HTTP path.

## Release operations

After a fresh successful verification:

```sh
.venv/bin/python -m tools.release build
.venv/bin/python -m tools.release inspect releases/v5.6.0-source.zip
.venv/bin/python -m tools.release stage releases/v5.6.0-source.zip
.venv/bin/python -m tools.release activate RELEASE_ID_FROM_STAGE
.venv/bin/python -m tools.release serve --port 8896
```

Stop the server before activating another release, then restart it. `python -m tools.release rollback` switches the pointer to the previous verified release. Each release ID has its own persistent synthetic state directory. Rollback is a local release/state demonstration, not a database schema migration or a hot swap. Checksums establish consistency with a manifest, not a signed publisher identity.

Source packages exclude local databases, environments, browser binaries and caches. Builds refuse stale verification and existing output filenames. Use a different explicit output directory for a release candidate. See OPERATIONS.md before staging an archive.

## GitHub and CI

The project has its own new private repository: [kilicerdal/healthcare-quality-lab](https://github.com/kilicerdal/healthcare-quality-lab). Existing projects and repositories are independent.

GitHub Actions installs dependencies and Chromium, runs regression and known-fault checks, builds and inspects a checksummed source archive, starts its staged Waitress runtime for an actual HTTP journey, and uploads evidence. Current remote execution results are recorded in the V5.6 report and `artifacts/v5.6/github-ci.json`. Earlier version evidence remains preserved. The hosted runtime target for this delivery is local loopback; the GitHub repository is private and is not a public website.

## AI tools and learning

Codex built this implementation. Ollama actually generated and explained local test data. ChatGPT, Copilot and Claude Code have optional exercises in the [AI tools playbook](docs/AI_TOOLS_PLAYBOOK.md) and [V5 learning guide](docs/LESSON_05.md); they are not represented as integrations that ran. VS Code workspace trust was not changed automatically.
