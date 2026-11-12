# Lesson 2 — A workflow is more than a calculation

V1 answered one question: what would this synthetic contract do with a claim request? V2 adds state: a claim is submitted, then approved, then paid in a simulated ledger. Remembering state means tests must check both what changes and what must stay unchanged.

## Follow one test

Read `test_complete_lifecycle_records_expected_payment_and_events` in `tests/unit/test_workflow.py`. Submission evaluates the coverage contract and creates revision 1. The adjuster approves, producing revision 2. Finance records the simulated payment, producing revision 3 and a ledger amount of 90000 cents. The test independently expects the ordered statuses and actors; it does not ask production code to invent its expected lifecycle.

## What a transaction means

Payment touches three records: claim status, ledger and history. They must either all commit or all roll back. If the ledger insert fails after the status update, keeping paid status would be misleading. Read `test_storage_failure_rolls_back_transition_ledger_and_event` and the test that injects failure during event insertion. Both compare the full evidence before and after failure.

## Why we test simultaneous requests

Two requests can both arrive before either finishes. A read-then-write guard alone can be unsafe. V2 takes an SQLite write transaction before checking and changing state, and the database also enforces unique IDs. The two-thread tests expect one success and one conflict for duplicate submission and payment. This is a bounded concurrency check, not proof of distributed exactly-once processing.

## Why fixtures matter more now

Each test receives a temporary database. Browser tests receive a temporary server using that database. A test cannot pass because another test already approved its claim, and a failed test does not pollute the interactive database. Connections and servers close after use; pytest retains some temporary files for debugging according to its own policy.

## Reusable test helpers

`tests/support/api_client.py` centralizes workflow routes and demo identity headers. `tests/support/workflow_page.py` centralizes browser selectors and actions. The test files still state expected statuses and money amounts. Helpers reduce duplication without replacing the independent assertions.

## Your exercise

Explain why evaluation decision approved can coexist with workflow status submitted. Predict the response to finance paying a submitted claim, to a second approval, and to another member reading a claim. Then run the corresponding focused tests. Finally, describe which records must remain unchanged after an injected storage failure.
