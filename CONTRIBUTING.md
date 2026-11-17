# Contributing

## Set up and verify

Use Python 3.11+ and a focused branch. From the repository root:

```sh
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.verify
```

On Windows, use `.venv\\Scripts\\python.exe`. Bootstrap installs local Python dependencies and Chromium; it does not install Ollama, download models, or require API credits. The normal suite uses offline provider doubles.

For a focused change, first run the affected unit/API/browser tests, then the full verification before a behavioral release. [Architecture](docs/ARCHITECTURE.md) · [Demo](docs/V5.8_DEMO.md) · [Dependency maintenance](docs/DEPENDENCY_MAINTENANCE.md).

## Preserve the evidence

Use synthetic identities, amounts and claims only. State business expectations independently of the implementation. Keep the reference checker independent; do not weaken an expectation to make a failure pass. Maintain transaction, replay, concurrency and rollback behavior.

Label authored fixtures, model-generated drafts and live experiments accurately. Model outputs remain unapproved until explicitly reviewed; edits invalidate review. Do not auto-apply or execute model-generated code. A dependency/documentation change does not make an old measurement a fresh run.

Live provider evaluation is optional and requires explicitly configured credentials and a budget. Never run paid calls as part of an ordinary test, page load, or dependency PR. Never commit keys, .env files, local databases, session records or unreviewed generated reports. Review screenshots and exported evidence for sensitive content.

## Submit a change

Explain the problem, resulting behavior, exact checks performed and any limits in the PR. Add a regression test when a behavior change needs one. Keep reports tied to the measured source; preserve historical results rather than overwriting them as current. Documentation-only changes need link/command checks, not claims of a new full regression.

Report security-sensitive details through [SECURITY.md](SECURITY.md). Original project code is MIT licensed; preserve third-party attribution.
