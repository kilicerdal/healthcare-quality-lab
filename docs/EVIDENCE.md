# Evidence provenance

Documentation review: **2026-11-17**. This date records a documentation/source review, not a rerun of every example.

## Read the labels

- **Current CI** means the workflow outcome for the specific commit shown in Actions. A moving badge is not an immutable release record.
- **Recorded local** means a saved execution under its original environment and date; a screenshot never reruns itself.
- **Historical release** means evidence for an older version. Its count and dependency versions must not be rewritten to resemble current CI.
- **Authored / deterministic** means an intentionally specified scenario or fixture. It is not a newly generated model output.
- **Recorded model experiment** means calls made under the saved protocol; it does not prove live provider availability or general accuracy.

[Current Actions runs](https://github.com/kilicerdal/healthcare-quality-lab/actions?query=branch%3Amain) · [Reviewer journey](REVIEWER_GUIDE.md) · [Supported setup](MAINTENANCE.md).

## Recorded evidence inventory

| Item | Label and scope | Inspect |
|---|---|---|
| 665 deterministic executions | Recorded local V5.8, November 17, 2026; Python 3.13.18, 538 unit / 81 API / 46 Chromium; no live model in core tests | [Original verification and source fingerprint](../artifacts/verification.json) |
| Engineering proof screenshot and scenario JSON | Recorded local V5.8, November 17, 2026; authored oracle/concurrency/recovery/reference-change examples, no paid calls | [Scenario observations](../artifacts/showcase/deterministic-evidence.json) |
| Provider comparison table | Recorded local V5.8, November 17, 2026; sixteen authored inputs, three trials per provider; eligibility is not approval | [Raw protocols, settings, results, budget and limits](../artifacts/showcase/provider-comparison.json) |
| Focused generation and final gap-map screenshots | Historical local V5.7 development cohort; 20 tasks and eleven defined predicates, not a blind holdout | [V5.7 report](V5.7_REPORT.md) |
| V5.8 recording/release report | Historical release evidence retained under its original version | [Release](https://github.com/kilicerdal/healthcare-quality-lab/releases/tag/v5.8.0), [report](V5.8_REPORT.md) |

The verification JSON stores a source fingerprint, not a Git commit. Do not substitute a containing commit for the execution's unknown commit. Its recorded dependency versions differ from today's pinned install requirements, so the saved result is not proof of those pins; fresh CI installs the current requirements.

## Audit the model experiment
Open `protocols`, `settings`, `limits`, `results`, `budget` and `rows` in the linked comparison JSON. They preserve input/prompt controls, recorded outputs and eligibility. The [evaluation protocol](V5.8_DEMO.md#live-provider-evaluation-is-separate) explains the known scenario families, matching base prompt/schema, differing transport/decoding and the absence of a blind holdout. Wrong or incomplete calculations are excluded from eligibility, not silently corrected. Trial repeats describe these settings; raw token-derived estimates and conservative ledger reservations are different cost measures, neither a billing invoice. No report or screenshot triggers a paid request.

## Immutable documentation snapshot

[Files as reviewed at `fb1b138a8f3e`](https://github.com/kilicerdal/healthcare-quality-lab/tree/fb1b138a8f3e811dd16d8bfa0cd231274b4096b6). This identifies the containing source snapshot, not an inferred capture commit. Historical artifacts are preserved unchanged.
