# V3 implementation plan

Work only in `/Users/erdalkilic/Documents/Healthcare Quality Lab`.

## Deliverable

A local AI Test Studio that sends requirements and selected synthetic contracts to Ollama and receives NEW structured test cases, not selections from a prewritten catalog.

## Build sequence

1. Preserve V2's verified source archive and evidence.
2. Define a strict declarative test format for evaluate, submit, transition and read actions, with explicit expected results.
3. Add a fixed-loopback Ollama provider with model allowlist, schema-guided generation, time/output limits and explicit errors.
4. Save exact prompts, settings, raw outputs, validation findings and proposal revisions in a project-local SQLite experiment store.
5. Add editable proposals, source/duplicate checks and an explicit reviewer-attestation gate. Edits invalidate approval.
6. Execute only approved snapshots with a fixed action budget in temporary databases, never the interactive claim store or arbitrary Python.
7. Build the browser studio, regression tests, live-model demonstration and versioned evidence export.
8. Produce a detailed V3 report explaining what was built, why, actual AI behavior, verified results and limitations.

## Boundaries

Schema validity and valid source IDs do not prove expected-result correctness. Reviewers must inspect the proposed oracle. Identity labels are demo attestations, not authenticated human identity. The AI has no shell, browser, network-action or direct database tools. Live model experiments are separate from deterministic CI tests. V4's broader held-out evaluation remains planned.
