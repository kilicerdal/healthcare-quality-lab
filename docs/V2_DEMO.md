# V2 demonstration guide

## Purpose

Show that a coverage answer and a completed claim workflow are different things. A valid claim must be owned, uniquely identified, reviewed in order and recorded atomically.

## Start

Run `python -m tools.verify`, then start the V2 app using the README command. Open `http://127.0.0.1:8892/#workflow`. Explain the demo identity disclaimer and the synthetic-only scope before showing ledger entries.

## Full workflow

Select Customer / M100. Generate a new ID, keep Medical and 100000 cents, and submit. The coverage evaluator returns a 90000-cent payout, but lifecycle status is submitted / revision 1. Select Adjuster / demo, inspect the same selected claim, and approve. Status is approved / revision 2. Select Finance / demo and record simulated payment. Status becomes paid / revision 3; exactly one $900 simulated ledger entry appears. The timeline shows the three actors and linked WF rules. Export JSON and compare the stored payout with the ledger amount.

## Negative scenarios

Try the same ID again with its owning customer: DUPLICATE_CLAIM leaves the existing record unchanged. Switch to Customer / M200: M100's claim disappears from this view. Staff can read all synthetic records; customer-only submission is disabled for staff. Select Finance before approval on a new submitted claim: payment is disabled, and API tests independently verify the server returns 409 if called directly.

For a denied submission, select Customer / M200, service Hospital and uncheck prior authorization. The server returns AUTH_REQUIRED and stores no claim. Recheck authorization and reuse the same ID successfully. Do not confuse an unsuccessful submission with a stored denied claim; V2 intentionally stores only accepted submissions.

## Evidence

Open `artifacts/workflow-benchmark.json` in VS Code. Show five faulty variants detected against passing references. Open `tests/unit/test_workflow.py` to inspect concurrent duplicate/payment and rollback tests. Explain that two-thread checks are not a load test.

## AI learning

Read the three real local-model suggestions in `artifacts/v2/ai-review.json`, then their engineering assessment. The suggestions repeat existing assertions while incorrectly saying the contracts omit those behaviors. This is a useful exercise in checking evidence, not proof that more models automatically improve the suite.

## Next

V3 will turn requirements into structured, source-linked AI proposals with an explicit review gate. V2 supplies the controlled application actions and reference assertions it will need.
