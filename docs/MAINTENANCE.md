# Compatibility, verification and dependency policy

## Supported setup

Python 3.11+; CI uses Python 3.13. Bootstrap installs the pinned pytest/Playwright dependencies and matching Chromium. SQLite is bundled with Python; no external database, Docker, paid provider or model runtime is needed for deterministic verification.

From a fresh checkout at the repository root, after installing those prerequisites:

```sh
python3 -m tools.bootstrap --browser
```

Python examples use POSIX virtual-environment paths; Windows uses `.venv\Scripts\python.exe`.

## Quick check and complete validation

Quick, bounded check:

```sh
.venv/bin/python -m pytest -m smoke -v
```

Complete deterministic checks:

```sh
.venv/bin/python -m tools.verify
```

[Architecture](../docs/ARCHITECTURE.md) · [Evidence and reproduction](../docs/V5.8_REPORT.md). The application is a synthetic teaching lab, not a payer system or compliance certification. Provider comparison cohorts are recorded separately; core CI uses offline doubles. Never rewrite a historical environment or model-result record to match a new dependency version.

Commands resolve pinned requirements/lockfiles where supplied. A runtime major or supported Python floor is a deliberate compatibility decision, not an automatic dependency update. Container major/patch tags can receive upstream updates unless an exact version is stated; this is not a bit-for-bit image reproducibility claim.

## Update decisions

Review recorded: **2026-11-17**. This is a policy review date, not a claim that every optional live integration was rerun that day. Current hosted execution appears in Actions; historical counts retain their dates and source identifiers.

No open dependency migration exceptions at the recorded review. Historical artifacts are excluded from pip Dependabot discovery; their versions describe the original runs, not install requirements.

Dependabot checks application/tool dependencies weekly and GitHub Actions monthly. Updates are reviewed in PRs and are not auto-merged. Monthly, review deferred PRs, runtime support, security advisories and the oldest open genuine defects. Record the tested version and run link before changing a compatibility boundary. Remove an ignore rule when its migration is approved; do not keep it silently forever. Security fixes may require raising a runtime floor rather than bypassing tests.

A green CI badge describes that workflow's current result, not a security, accessibility or production-readiness certification. Framework and license badges identify tools/terms, not test results. Do not publish a static passing test-count badge without a dated run.
