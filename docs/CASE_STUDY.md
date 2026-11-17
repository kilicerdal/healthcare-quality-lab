# Healthcare Quality Lab: testing the tests

A passing test is useful only when its expectations are worth trusting. This project makes that problem visible: a synthetic healthcare workflow, AI-created cases, an independent reference calculation, explicit review and a controlled defect campaign.

## The business behavior

The application evaluates invented plan rules, persists claims, enforces demo ownership and role rules, and records approval and simulated payment history. Money uses integer cents. Tests check the stored result and history, not just a successful response.

## The hard part: an AI answer can look complete and still be wrong

Earlier generation experiments omitted observations and produced incorrect numeric expectations. Adding more assertions did not automatically improve correctness. Those failures remain in the [version reports](V5.7_REPORT.md).

The response was to separate generation from trust:

- Retrieve a bounded set of written rules and one relevant plan.
- Request visible structured calculations and validate their shape.
- Compare the expected result with a separate standard-library reference model.
- Require explicit review tied to the exact case snapshot.
- Clear approval after edits, corrections or source changes.
- Run only the bounded declarative case language against disposable state.

The model cannot run arbitrary Python or change application code. A confirmed reference replacement is labeled separately from an original model answer.

## What changed in the measured demonstration

The retained V5.5 two-case suite detected **2/12** known fault seeds. Later work targeted surviving defects and strengthened observations. In V5.7, the AI-derived core suite detected **12/12**: one original AI workflow and one evaluator assembled from seven reviewed focused outputs.

Local `qwen3.5:27b` produced correct first-attempt assertions/calculations for **20/20 frozen development tasks**, without correction or reference replacement. The final four-case showcase also closed the remaining gaps among eleven defined scenario predicates.

These are bounded results. The cohort was used during development; both model and prompt changed from earlier pilots. This is not a blind holdout, a general AI accuracy score or proof that every possible defect is detected. Errors do not earn detection credit.

## Evidence and code

- [Recorded measurement](../artifacts/v5.7/focused-measurement.json)
- [Detailed methodology and failures](V5.7_REPORT.md)
- [Recorded focused-generation screenshot](../artifacts/v5.7/focused-panel-desktop.png)
- [Recorded final showcase screenshot](../artifacts/v5.7/showcase-desktop.png)
- [Independent reference model](../healthcare_quality/reference.py)
- [Review and execution controls](../healthcare_quality/ai_studio.py)
- [Coverage and known-fault scoring](../healthcare_quality/coverage_lab.py)
- [Guided local demo](V5.7_DEMO.md)

The retained V5.7 regression recorded **622 tests** across unit, API and Chromium layers. Current V5.8 verification records **665 tests**. It uses offline provider doubles. Actual local model measurements are separate. The runtime stays on loopback, uses invented data and does not claim production authentication or healthcare compliance.

The engineering value is the chain of evidence: a proposal, an independently checked expectation, a reviewed snapshot, a healthy control and an observed defect. Each link can be inspected.


## V5.8: prove payment integrity and inspect provider failures

The new engineering proof page runs two actual concurrent HTTP payment requests, demonstrates rollback after a real worker-process interruption, and exposes request IDs and committed history. An isolated requirement change exercises the actual stale-review execution guard. These authored demonstrations use disposable state; they do not claim model generation.

A new sixteen-input, three-trial provider evaluation separates expected outcomes from calculation records. Both OpenAI GPT-6.1 Terra and local qwen3.5:27b matched all 48 literal expected outcomes. OpenAI matched all 48 calculation records; six local outputs had wrong or incomplete calculation fields and were blocked. Eligible outputs were never automatically approved or executed. This small cohort and differing runtime settings do not establish a general provider ranking.

The comparison cost estimate was $0.04056, or $0.04218 including a separate pilot. A persistent $15 ledger retained $2.68744 in conservative reservations. Token-derived estimates, reservations and billing invoices are distinct.

[Current report](V5.8_REPORT.md) · [Two-minute guided demo](V5.8_DEMO.md) · [All recorded trials](../artifacts/showcase/provider-comparison.json)
