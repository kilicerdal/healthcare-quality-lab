# Healthcare Quality Lab — V5.7

A quality engineering portfolio built with **Python, Flask, SQLite, pytest, Playwright and local Ollama**.

The central question is simple: **does a test detect the wrong business result, or does it only pass?** This lab follows synthetic claims from evaluation through approval and payment, checks AI-created expectations against an independent reference model, and measures reviewed tests against known defects.

**Synthetic data only.** Plan amounts, demo identities and payments are invented. This is a local teaching application, not a real payer system or a compliance certification.

**Start here:** [Case study](docs/CASE_STUDY.md) · [Guided demo](docs/V5.7_DEMO.md) · [Code examples](#review-the-code) · [Run locally](#run-locally)

## Results you can inspect

| Evidence | Recorded result | What it means |
| --- | --- | --- |
| Deterministic regression | **622 passed:** 510 unit, 70 API, 42 Chromium | Offline provider doubles; actual browser flows. [Fresh publication verification](docs/PUBLICATION_REVIEW.md#verification) |
| Focused local AI generation | **20/20** correct first-attempt assertions/calculations | A frozen development cohort using local `qwen3.5:27b`; zero corrections or reference replacements. [Measurement](artifacts/v5.7/focused-measurement.json) |
| Reviewed AI-derived core suite | **12/12** known fault seeds detected | One original AI workflow plus an evaluator assembled from seven reviewed model outputs. Known seeds, not exhaustive defect coverage. [Report](docs/V5.7_REPORT.md) |
| Final guided showcase | **0 remaining gaps** among 11 defined scenario predicates | The four-case final suite closes this particular gap map. It does not establish complete application coverage. |

[Recorded GitHub Actions run](https://github.com/kilicerdal/healthcare-quality-lab/actions/runs/43314919548) passed on the previously recorded implementation fingerprint. Current checks appear in the [Actions tab](https://github.com/kilicerdal/healthcare-quality-lab/actions). Local model experiments and deterministic CI are separate evidence.

![Recorded focused-generation panel showing the twenty-task development cohort](artifacts/v5.7/focused-panel-desktop.png)

*Recorded V5.7 local experiment. These are observed development results, not a fresh model run or a blind benchmark.*

![Recorded final showcase with known-fault detection and the defined gap map](artifacts/v5.7/showcase-desktop.png)

## Review the code

| Example | Engineering decision |
| --- | --- |
| [Claim evaluator](healthcare_quality/claims.py) and [workflow](healthcare_quality/workflow.py) | Explicit business rules, persisted state, ownership checks, duplicate protection and ordered payment history |
| [Independent reference model](healthcare_quality/reference.py) | Expectations are calculated separately from the application under test |
| [AI review and execution](healthcare_quality/ai_studio.py) | Hash-bound approvals, fresh review after edits, isolated execution and retained provenance |
| [Coverage and defect scoring](healthcare_quality/coverage_lab.py) | Healthy controls first; assertion mismatches earn detection credit, infrastructure errors do not |
| [Operation recovery](healthcare_quality/operations.py) | Persisted heartbeat leases and fenced completion after interruption |
| [Unit tests](tests/unit), [API tests](tests/api), [browser tests](tests/e2e) | Different layers verify business behavior and the actual UI |
| [CI workflow](.github/workflows/ci.yml) and [release tooling](tools/release.py) | Regression, source integrity checks and a staged runtime rehearsal |

## Run locally

Requires **Python 3.11+**; the recorded delivery used Python 3.13.

```sh
git clone https://github.com/kilicerdal/healthcare-quality-lab.git
cd healthcare-quality-lab
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.serve --port 8895
```

Open [the local guided showcase](http://127.0.0.1:8895/#showcase). On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Bootstrap installs project-local dependencies and Chromium. It does not install Ollama or download models. **The deterministic tests do not require a model or paid API credits.** Running actual AI generation is optional and requires your own local Ollama service and an allowed installed model.

```sh
.venv/bin/python -m tools.verify
.venv/bin/python -m pytest -m smoke -v
.venv/bin/python -m pytest -m e2e --headed --slowmo 350
```

## How AI cases become executable tests

1. Request bounded declarative proposals from local Ollama using selected written contracts.
2. Inspect inputs, assertions, retrieved sources and independent reference checks. Wrong or incomplete expectations block approval.
3. Explicitly review the snapshot. An edit, correction or reference replacement clears approval and requires fresh review.
4. Execute approved cases against disposable SQLite databases, then compare healthy behavior with known fault seeds.

The model has no shell, browser, database or arbitrary network tools. The case language permits only evaluate/submit/transition/read, with at most four cases and eight steps per case. Generated Python is not executed. Reviewer labels are local attestations, not authenticated human identities.

## Scope and limitations

- The 20-task AI result is a development demonstration. The model and prompt both changed from earlier pilots; the result cannot be attributed to prompting alone.
- Failed small-model pilots, incorrect drafts and surviving faults remain in the historical evidence.
- Twelve known seeds and eleven scenario predicates define the measured scope. They do not prove general model accuracy or complete defect detection.
- Demo actor headers and reviewer labels are not production authentication. Keep the runtime on loopback; do not expose it to the internet or enter real patient data.
- Public source availability does not mean a publicly hosted application. No production deployment, healthcare compliance or accessibility certification is claimed.

## Reports and release operations

Read the [case study](docs/CASE_STUDY.md), [architecture](docs/ARCHITECTURE.md), [operations guide](docs/OPERATIONS.md) and [publication review](docs/PUBLICATION_REVIEW.md).

Historical reports: [V5.1](docs/V5.1_REPORT.md) · [V5.2](docs/V5.2_REPORT.md) · [V5.3](docs/V5.3_REPORT.md) · [V5.4](docs/V5.4_REPORT.md) · [V5.5](docs/V5.5_REPORT.md) · [V5.6](docs/V5.6_REPORT.md) · [V5.7](docs/V5.7_REPORT.md).

After fresh verification, build and inspect a source package:

```sh
.venv/bin/python -m tools.release build
.venv/bin/python -m tools.release inspect releases/v5.7.0-source.zip
```

The operations guide covers staging, activation and rollback. Packages exclude local databases, environments, browser binaries and caches. Checksums establish integrity, not a signed publisher identity.

## AI provenance

Codex built the implementation. Ollama performed the recorded local generation experiments. Optional ChatGPT, Copilot and Claude Code exercises are described in the [AI tools playbook](docs/AI_TOOLS_PLAYBOOK.md); they are not represented as integrations that ran.

## License

No open-source license has been granted for this project's original code. It is published for portfolio review; public visibility does not grant a general reuse license. Third-party dependencies retain their own licenses.
