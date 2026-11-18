# Showcase upgrade acceptance checklist

- [x] Fresh-clone, disposable demo state with no historical experiment-ID dependency.
- [x] Wrong AI expectation blocked, explicit correction/review path, known-defect evidence.
- [x] Actual competing HTTP payment requests, exactly one ledger entry and consistent history.
- [x] Actual interrupted worker, rollback, retry and rejected replay with unchanged state.
- [x] Independent literal calculation examples and invariant checks; shared-fixture limits stated.
- [x] Requirement-change impact and real stale-review guard behavior.
- [x] Investigation view: input, rule, expected/actual, timeline and request IDs where applicable.
- [x] Current public metadata and current evidence links/freshness.
- [x] Explicit OpenAI/Ollama comparison on a newly frozen cohort, repeated trials and failures retained.
- [x] Persistent fail-closed $15 maximum API budget, no hidden retries, token usage and cost evidence.
- [x] Captioned actual walkthrough and short recruiter narrative.
- [x] Offline unit/API/browser regression; release package inspection and runtime rehearsal.
- [x] Public docs and final report match measured evidence and actual spend.

Normal CI and page loads must never invoke a paid provider. Generated expectations remain untrusted. No new live result is claimed until observed. Original local stores and unrelated edits remain untouched.
