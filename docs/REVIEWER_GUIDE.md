# Reviewer journey

## What this demonstrates
Synthetic claim evaluation leads to approval and a simulated payment. The same claim connects the business-rule and concurrency/recovery stories: the amount must be independently correct, and the approved payment must commit only once. This is a local teaching lab, not a payer system.

## Start and inspect
From a clean checkout with Python 3.11–3.13:

```sh
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.demo --state-dir .local/reviewer-demo --port 8895
```

Use a new directory for each rehearsal; the launcher refuses existing nonempty state. On Windows use `.venv\Scripts\python.exe`.

1. Open http://127.0.0.1:8895/#proof and run the plausible wrong expectation. The independent reference blocks the calculation that ignores the deductible; the healthy control must pass before a seeded defect earns credit.
2. Run competing payment requests. Inspect HTTP 200/409, one committed payment and ordered history.
3. Interrupt the worker before commit, compare unchanged approved state, retry successfully, then reject replay.
4. Inspect the requirement-change example: an old review cannot authorize a changed reference.

## What the result means
Expected/observed values come from actual authored scenarios against disposable SQLite state. These are deterministic demonstrations, not fresh model outputs. An infrastructure error is not a detected business defect. [Two-minute script and provider protocol](V5.8_DEMO.md).

## Reproduce the checks

```sh
.venv/bin/python -m pytest -m smoke -v
.venv/bin/python -m tools.verify
```

Full verification includes browser checks and the known evaluation/workflow seeds. It requires Chromium, but no paid key or model. [Compatibility matrix](MAINTENANCE.md) · [Evidence provenance](EVIDENCE.md) · [Architecture](ARCHITECTURE.md).

[How this project complements the portfolio](https://github.com/kilicerdal/eai-engineering/blob/main/docs/PROJECTS.md).
