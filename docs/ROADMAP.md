# Five version implementation roadmap

All five versions belong to the same standalone Healthcare Quality Lab project. Versions are milestones, not new folders inside other projects. We implement and report one version at a time; V1–V4 are delivered milestones. V5 adds local verified releases and a separate private GitHub repository; final verification evidence is recorded in V5_REPORT.md.

## V1 — Reliable foundation

Purpose: understand the system and its test oracle before evaluating AI suggestions.

Deliverables: eight synthetic coverage configurations, seven written rules, a stateless Python evaluator, local Flask interface, rule trace, JSON export, pytest unit/API tests, Chromium browser tests, smoke/sanity/regression selectors, a seven-seed defect experiment, an optional local AI contract review, VS Code setup, and a ready-to-push CI definition.

Acceptance: all recorded tests pass without skips; all seven authored defect seeds are detected against a passing reference; user can inspect a trace and run the documented demo; final evidence and detailed report are saved. A live model review is optional for core execution and is recorded separately.

## V2 — Broader healthcare workflows — delivered

Purpose: move from one stateless evaluation to isolated, repeatable claims workflows.

Delivered: nine synthetic member/policy fixtures, claim IDs and duplicate handling, submitted/approved/paid transitions, demo role and ownership checks, SQLite persistence, a simulated payment ledger, atomic event history, additional plan scenarios, reusable page objects/API clients, isolated test databases and saved execution evidence. Six explicit workflow contracts define the behavior. Dates and accumulators remain outside the model.

Acceptance: positive and negative lifecycle tests preserve state correctly; duplicate submissions cannot create duplicate payments; permissions and setup/cleanup are verified; evidence links requirements to scenarios and outcomes. Deliver a V2 report explaining the new complexity and results.

## V3 — Local AI-generated test proposals — delivered

Purpose: learn how a model turns a requirement into a reviewable proposal.

Delivered: fixed-loopback Ollama generation, prompt and schema provenance, new declarative cases, source/duplicate/observable checks, assumption and missing-oracle warnings, persisted edits, explicit reviewer attestation, revision/hash-bound approval, isolated action execution, expected-versus-observed evidence and trusted pytest export. Reviewer labels are local attestations, not authenticated human identity. No arbitrary generated Python is executed.

Acceptance: valid novel proposals can be reviewed and executed through permitted actions; invalid or ungrounded proposals are blocked; no test runs before approval; provider failure is explicit; raw output, model/settings and reviewer changes are recorded. Compare tools using common tasks. Deliver a V3 report.

## V4 — Evidence, investigation and AI evaluation — delivered

Purpose: measure usefulness and errors rather than relying on impressive-looking text.

Delivered: authored evaluation examples with a reserved split, frozen paired prompts, lexical retrieval, fact-versus-hypothesis explanations, engineering correction audit, assertion sensitivity and separate quality metrics. Add embeddings or vector search only if the documentation size and retrieval evaluation justify them.

Acceptance: experiment provenance is reproducible at the recorded-input level; expected results are independently checked; reports distinguish model quality from authored fixture benchmarks; unsupported explanations can return insufficient evidence. Deliver a V4 report with measured limitations.

## V5 — Release and showcase

Purpose: demonstrate a complete, repeatable engineering workflow.

V5 scope: the new private kilicerdal/healthcare-quality-lab repository, actual GitHub CI, checksummed versioned packages, verified local activation and rollback, timeout/failure tests, readiness and request IDs, and a guided presentation. The chosen runtime target is local loopback; no public hosting is implied.

Acceptance: required checks run on the remote repository; artifacts and release provenance are accessible; deployment and rollback are verified for the selected target; all claims in the final demonstration have supporting evidence. Deliver a V5 report and final architecture narrative.

## AI learning across versions

Codex: implement, explain and review. Ollama: local review in V1 and generation in V3. ChatGPT: requirements and test-design exercises. Copilot: editor-based test proposals. Claude Code: alternate review and repository reasoning. Document actual access and execution separately from exercises. Accounts, subscriptions and installed tools may differ; no paid service or new account is assumed.

## V6.3–V6.7 combined delivery

V6.3 extends bounded AI cases into advanced benefits with a separate lifecycle oracle and explicit review. V6.4 freezes raw/corrected evaluation and scenario-preservation controls. V6.5 adds an owner-only ephemeral local-model CI runner. V6.6 supplies the interview narrative, editable personal deck, recorded UI demonstration and tagged release assets. V6.7 adds real HTTP synthetic eligibility/payments, durable outbox/inbox and reconciliation faults. These are milestones in one combined V6.7 release. Each has a detailed report; previous public releases and archives remain unchanged.


## V6.8–V7.0 completed implementation milestones

- V6.8: plan-first test design, focused retrieval and separate AI/calculator expectation authorship. [Report](V6.8_REPORT.md).
- V6.9: sealed advanced failure evidence, actual pricing-fault restoration and citation-scored optional AI hypotheses. [Report](V6.9_REPORT.md).
- V6.10: versioned requirement/assertion/execution graph and non-mutating what-if maintenance impact. [Report](V6.10_REPORT.md).
- V6.11: actual production-pricing AST mutation comparison, seeded properties, lifecycle metamorphic relations and bounded prefix reduction. [Report](V6.11_REPORT.md).
- V6.12: frozen model/prompt matrices with request budgets, exposure history, interruption/cancellation fencing and original answers. [Report](V6.12_REPORT.md).
- V7.0: fresh guided showcase, six reports, separate editable interview presentation, captioned actual browser capture and verified combined release. [Guide](V7.0_DEMO.md), [report](V7.0_REPORT.md).

These are six implementation milestones delivered in one combined V7.0 release. We do not invent six independently deployed runtimes or claim that the observed prompt experiment improved raw model accuracy.

## V7.1–V8.0 implementation track

Ten milestones extend the same standalone application: V7.1 installation diagnostics; V7.2 input-design quality; V7.3 family-separated frozen evaluation; V7.4 eight synthetic coverage packs; V7.5 seven complete lifecycle journeys; V7.6 two installed HTTP observation adapters; V7.7 authorization, dependency and resilience evidence; V7.8 bounded evidence assistant and explicit local AI planning; V7.9 ownership routing and portable evidence bundles; V8.0 integrated workbench, learning guide and reproducible delivery. Each has its own detailed report. Current measured outcomes and limitations are recorded in docs/V7.1_TO_V8.0_DELIVERY_REPORT.md; no milestone is a claim of healthcare compliance or production readiness.
