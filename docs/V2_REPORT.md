# Healthcare Quality Lab V2 Engineering Report

**Version:** 2.0.0 — Healthcare workflows

**Implementation date:** November 11, 2026, America/New_York

**Project:** `/Users/erdalkilic/Documents/Healthcare Quality Lab`

**Outcome:** V2 extends the working V1 evaluator into a persistent, synthetic claim workflow. Customers submit owned claims, adjusters approve them, and finance actors record one simulated payment. SQLite keeps state, events and ledger changes consistent. The final local suite passed 184 tests, and all twelve authored evaluation/workflow fault experiments were detected. The implementation, evidence, local-model review and limitations are documented below.

## 1 Why we built V2

V1 established a reliable answer to a narrow question: what does a written synthetic coverage contract say about one request? It could evaluate a claim, show a payout and explain a denial through a rule trace. It deliberately forgot that request afterward. That was appropriate for learning assertions, but it could not represent the work involved in processing a claim over time.

A professional quality framework must also investigate sequences. Can the same claim be submitted twice? Can a customer access another member's record? Can finance pay before an adjuster approves? What if storage fails after the status changes but before a ledger entry is saved? Those are workflow risks, not just arithmetic risks.

V2 creates a controlled system where we can answer those questions through observable behavior. It introduces state only after defining explicit contracts, then tests successful paths, rejected actions, storage failures and simultaneous requests. The purpose is to connect test design to business risk and show that the framework can detect violations of those contracts.

This also prepares for V3. An AI-generated test proposal needs permitted actions, stable request schemas, known identities, isolated setup and an independent way to judge the result. V2 supplies those building blocks. It does not yet allow a model to invent and automatically execute tests.

## 2 Where the work happened and how V1 was preserved

All implementation changes were made in the standalone Healthcare Quality Lab folder shown above. No existing Generative AI framework, Insurance claim framework or other neighboring project was used as the destination, copied into this project, or modified during V2. Python dependencies and Chromium remain project-local. Temporary authoring scripts were staged in `/private/tmp`; the application does not require them.

Before changing V1 code, I created `releases/v1.0.0-source.zip` with a SHA-256 manifest and preserved the then-current evidence under `artifacts/v1/`. The archive excludes environments, browser binaries, caches and runtime data. It retains the V1 source, documentation and recorded evidence, so the earlier implementation is recoverable without confusing a historical report with the current application.

The original `docs/V1_REPORT.md` and HTML report remain historical snapshots. The current `/report` route serves V2; `/reports/v1` still serves the preserved V1 report. V1 and V2 are milestones in one standalone project, not new nested projects or copies placed into unrelated folders.

The interactive V2 database is `.local/claims-v2.sqlite`. It is excluded from source snapshots and Git tracking. Automated tests use different, temporary database paths; they do not reset or populate that interactive database.

## 3 What changed from V1 to V2

| Capability | V1 | V2 |
| --- | --- | --- |
| Coverage evaluation | Stateless Python decision and rule trace | Retained with the same seven teaching contracts |
| Member and policy fixtures | Caller-selected evaluation inputs | Nine named synthetic members linked to eight plan configurations |
| Claim identity | No saved claim | Persistent, globally unique, case-sensitive claim IDs |
| Roles | No lifecycle permissions | Twelve named demo actors across customer, adjuster, finance and auditor roles |
| Lifecycle | No remembered status | submitted → approved → paid |
| Payment | Evaluation payout only | Unique simulated ledger row matching the stored payout |
| Evidence | One request/response export | Stored evaluation, workflow history, revisions and ledger export |
| Test architecture | Direct tests and basic fixtures | Isolated databases, reusable API client and Playwright page object |
| Local verification | 101 passing cases, eight browser checks | 184 passing cases, 16 browser checks |
| Authored fault experiments | Seven evaluation seeds | Seven retained evaluation seeds plus five workflow seeds |

The original eight plan configurations and seventeen service categories remain. Their invented $100 deductible and $2,000 per-evaluation cap are unchanged. Adding persistent records does not make those figures real Medicare or commercial benefits.

## 4 The domain fixtures and why the server owns policy selection

The member fixtures span commercial PPO/HMO, Medicare A, B, C/Advantage and D, dental and vision. One Part B member is intentionally inactive, while another active Part B member supports a positive workflow test. This gives nine member fixtures for eight plan configurations. These are synthetic identifiers such as M100 and M200, not real people.

Each customer actor maps to exactly one member. Three staff actors provide adjuster, finance and read-only auditor behavior. A customer submits a member ID, service, amount and optional network/authorization/formulary flags. The server resolves the plan and active status from the trusted fixture, rather than accepting a body field such as role, active or plan_id.

This design creates a testable ownership boundary. If a request could simply declare its own role or active policy, a happy-path test might pass while the permission rule was meaningless. V2 rejects those extra fields and independently checks the actor's member association.

The identity header is `X-Demo-Actor`. The browser lets the demonstrator choose it. That is intentionally a simulation of role behavior, not authentication or protection against a person deliberately selecting a staff identity. Real login, sessions, identity verification and production authorization remain outside V2.

## 5 The six workflow contracts

The seven existing HC rules still define individual coverage evaluations. Six new WF rules define what happens around those evaluations. Keeping the two groups separate avoids treating a coverage decision as a completed operational approval.

| Rule | Contract | Risk addressed |
| --- | --- | --- |
| WF-001 | Known demo identities, customer ownership and role restrictions | Unauthorized read, creation or transition |
| WF-002 | Valid submission, unique ID, server-resolved policy and rejected-submission behavior | Duplicate or invalid stored claims |
| WF-003 | Ordered lifecycle and revision updates | Skipping approval, repeated actions or invalid states |
| WF-004 | One simulated ledger entry with the stored payout amount | Replay or incorrect simulated payment |
| WF-005 | Ordered successful events and preserved evaluation provenance | Unexplained changes or lost evidence |
| WF-006 | Transactional persistence, rollback, concurrency and test isolation | Partial writes or contaminated results |

`healthcare_quality/data/workflow_rules.json` contains the exact wording. `tests/data/workflow-traceability.json` links every WF rule to named tests. A metadata check verifies that those linked test functions exist. The mapping is a navigational aid, not a code-coverage percentage or proof of exhaustive requirement coverage.

## 6 The distinction between evaluation and lifecycle approval

A successful coverage evaluation means the request passed the synthetic HC rules. On submission, that evaluation is saved with a new claim whose lifecycle status is submitted and whose revision is 1. The adjuster has not acted yet.

An adjuster may move a submitted claim to approved, producing revision 2. Finance may then move approved to paid, producing revision 3 and a simulated ledger entry. A customer cannot approve their own claim. An adjuster cannot record payment. Finance cannot skip the submitted-to-approved step. An auditor can read but cannot perform those actions.

Only approved and paid are valid transition targets. A well-formed attempt to repeat an action or move from the wrong state returns a conflict; a malformed target returns a request error. Wrong-role actions are rejected before checking the current state. Failed actions preserve the prior status, revision, successful-event history and ledger.

For the normal M100 example, the stored evaluation has a 90000-cent payout. Submission records that amount but does not create a payment. Payment later records exactly 90000 cents in the simulated ledger. A zero-payout accepted claim can also complete the lifecycle and create one zero-amount ledger entry; that boundary is explicitly tested.

## 7 Why SQLite and how persistence works

V2 uses SQLite through Python's standard-library `sqlite3` module. It requires no new database server, cloud account or pip dependency in the verified environment. That keeps the project local while adding genuine persistence and transaction behavior. The official [Python SQLite documentation](https://docs.python.org/3/library/sqlite3.html) describes this embedded database interface.

Three tables hold the workflow: claims stores the current status, revision, normalized request and evaluation snapshot; events stores successful actions in revision order; payments stores one simulated ledger row per claim. Foreign keys connect the records. Unique constraints protect claim IDs, payment claim IDs and claim/event revisions.

Every operation opens its own connection, enables foreign keys and closes the connection afterward. Mutations begin an immediate write transaction before checking and changing stored state. SQLite serializes these writes. The service commits on success and rolls back on exceptions. Reads use a transaction so claim detail, events and payment are read as one consistent snapshot.

The claim stores both the evaluation contract hash and the workflow contract hash. The evaluation hash identifies the unchanged plan/rule fixtures. The workflow hash identifies the WF contracts, member fixtures and demo actors. A separate source fingerprint identifies the implementation and tests used for verification. These hashes identify content; they do not authenticate authorship or make a local database tamper-proof.

## 8 Atomicity and why partial writes are dangerous

Recording payment updates three things: claim status, a ledger row and a successful event. If one succeeds without the others, the record can become misleading. A paid claim without its ledger or a ledger entry without its history would undermine both the application and a test report based on it.

V2 places those changes in one transaction. Tests deliberately fail a payment insert after the status update and compare the full evidence before and after the exception. Another test fails the event insert after the ledger write. In both cases, the transaction must roll back every change, leaving the claim approved, its revision unchanged, no new ledger entry and no payment event.

The API converts SQLite operation failures into a 503 STORAGE_ERROR response without exposing the underlying SQL message. Unit tests inspect the raised database exception; API tests inspect the HTTP response and confirm that subsequent reads still show the original evidence. The point is not that every failure becomes recoverable automatically, but that a failed operation does not leave a half-completed workflow.

## 9 Duplicate protection, retries and concurrency

A successfully stored claim reserves its case-sensitive ID globally across members. A duplicate valid submission returns 409 DUPLICATE_CLAIM and changes nothing. Input validation happens first; for a structurally valid request, an existing ID conflicts before a new coverage denial is considered. Tests cover an existing ID resubmitted with an unsupported service as well as duplicates across two members.

A rejected coverage evaluation returns 422 and stores no claim, event or ledger row. Its ID can be corrected and reused. This makes it possible to submit an Advantage hospital request without authorization, observe AUTH_REQUIRED, correct authorization and submit successfully using the same ID.

Concurrent tests release two threads together. For same-ID submissions, one must create the claim and the other must conflict. For payment attempts on the same approved claim, one must complete and the other must see an invalid transition. The final record must have one ledger entry and three events. A separate constraint test attempts a second ledger insert directly and expects the database to reject it.

These checks cover two simultaneous local attempts, not distributed processing or sustained load. SQLite write serialization and unique constraints support this bounded demonstration. V2 does not promise exactly-once delivery of external requests or real payments. Repeating a completed transition is rejected rather than treated as a new successful idempotent request.

## 10 The new browser workflow desk

The Claim lifecycle tab contains the identity selector, current permissions, submission form, saved-claim list, detailed record, event timeline and workflow evidence export. It visually separates customer submission, adjuster approval and finance simulation. The selected claim can be retained when changing to an actor who may view it.

The form shows the member/policy fixture resolved for the customer. Staff cannot submit through that form. Approval and payment buttons are enabled only when the current actor and status permit the action. Server checks still enforce the rules independently; disabling a button is not the authorization mechanism.

Changing actors clears old detail immediately and refreshes the permitted view. The browser also ignores late results from a previous view generation so an older response is not rendered into a different actor's view. Customers see only their own records; staff see the latest 100 synthetic records. There is no pagination in V2.

The detail view shows lifecycle status, revision, evaluated payout, ordered events and the simulated ledger entry. Exported JSON contains the complete stored evaluation and workflow evidence. The original coverage evaluator, coverage explorer, rulebook and roadmap remain available. The rulebook now displays seven HC contracts and six WF contracts.

## 11 Reusable testing components and isolation

`tests/support/api_client.py` centralizes workflow endpoint paths and identity headers. Tests can use `as_actor` to express a permission scenario without duplicating request setup. It contains no payout formula or expected result, so the assertions remain independently visible in the tests.

`tests/support/workflow_page.py` provides a small Playwright page object for opening the desk, changing actors, submitting and selecting claims, approving and simulating payment. The browser tests still state their expected statuses, amounts and event counts. This follows the purpose described in Playwright's [page object guidance](https://playwright.dev/python/docs/pom): centralize repeated interface actions and selectors rather than hide the correctness criteria.

Each unit workflow fixture and API application gets a temporary SQLite file. Each browser test gets a temporary server and its own database. Tests do not depend on a previous scenario's saved approval and do not wipe the interactive database. Connections close after each operation; server fixtures shut down and join their threads at teardown.

Pytest may retain temporary test directories for debugging under its retention policy. That is different from using a persistent application database. The benchmark uses dedicated temporary directories that are removed when each experiment finishes. Flask's [testing documentation](https://flask.palletsprojects.com/en/stable/testing/) explains the application-factory and fixture patterns used here.

## 12 The API contract and its error meanings

| Endpoint | Purpose | Key outcomes |
| --- | --- | --- |
| GET /api/workflow/fixtures | Load synthetic members and named actors | 200 with an explicit demo-identity disclaimer |
| POST /api/claims | Submit an owned claim | 201 created; 400 malformed; 403 forbidden; 409 duplicate; 422 coverage denied |
| GET /api/claims | List records visible to the selected actor | 200 with latest 100 visible records; 403 for unknown identity |
| GET /api/claims/{id} | Inspect stored claim, events and ledger | 200; 403 wrong owner; 404 unknown claim |
| POST /api/claims/{id}/transitions | Approve or simulate payment | 200; 400 invalid target; 403 wrong role; 409 wrong state |
| GET /api/claims/{id}/evidence | Export the stored evidence object | Same ownership rule as detail |
| POST /api/evaluate | Retained stateless HC evaluation | Business denial remains a 200 evaluation response; malformed input is rejected |
| GET /report and /reports/v2 | Read the current detailed report | V2 HTML report |
| GET /reports/v1 | Read the historical report | Preserved V1 HTML report |

The difference between 200 evaluation denial and 422 submission denial is intentional. The evaluator successfully answered a question about coverage; the workflow refused to create a claim from that answer. Error responses include the relevant rule ID, and denied submissions include the evaluation evidence in their API details.

The application still imposes a 16 KiB request limit and requires JSON for writes. It does not accept a request field that enables internal defect modes. The simulated workflow is local and does not contact a payer or financial service.

## 13 The final verification results

The recorded run completed at 2026-11-11T21:51:45.802085-05:00 using `python -m tools.verify`.

| Check | Recorded result |
| --- | --- |
| Total automated cases | 184 passed, 0 failed, 0 skipped |
| Unit cases, including AI adapter mocks | 135 passed |
| API cases | 33 passed |
| Real Chromium browser cases | 16 passed |
| Original golden business examples | 28 reference examples, zero mismatches |
| Evaluation fault experiment | 7 out of 7 authored seeds detected |
| Workflow fault experiment | 5 out of 5 authored seeds detected, zero reference failures |
| Smoke selector | Six selected cases across Python, API and browser layers |
| Sanity selector | Six selected cases across authorization and duplicate behavior |
| Verification duration | 15.83 seconds on the tested machine |
| Remote GitHub Actions | Not executed |

The eight new browser cases cover the customer/adjuster/finance workflow, duplicate rejection, denied submission and correction, owner scoping, authorization correction, reload persistence with auditor controls, workflow export and mobile workflow behavior. The eight retained browser scenarios cover the evaluator and its supporting interface, with version/report expectations updated for V2.

The unit/API suite additionally checks malformed requests, overposted role/policy fields, missing identities, bad targets, cross-member access, replay, concurrent actions, storage rollback, isolated databases, fixture consistency, preserved evaluation snapshots and traceability links. The package version is 2.0.0; Python 3.13.18, pytest 8.4.2, Playwright 1.56.0 and Flask 3.1.2 were used.

The evidence is in `artifacts/verification.json`, JUnit XML, raw pytest output, both benchmark files and desktop/mobile screenshots. The final source SHA-256 is `61231c939399095cffd97c19bb85e7640e0aba5f6213f7cc33d234278071207c`. Screenshots and automated flows were inspected, but this is not a full accessibility audit, production load test or code-coverage measurement.

## 14 What the five new fault experiments prove

| Internal faulty variant | Required reference behavior | Observed faulty behavior |
| --- | --- | --- |
| Ownership bypass | Other customer's detail request returns 403 | The record becomes accessible |
| Duplicate replay accepted | Duplicate submission returns DUPLICATE_CLAIM | Existing record is returned as accepted |
| Approval skipped | Finance cannot pay submitted status | Claim moves directly to paid |
| Ledger amount corrupted | Ledger equals stored 90000-cent payout | Ledger records 180000 cents |
| History omitted | Full lifecycle has three successful events | Only the submission event remains |

Each experiment runs against a fresh reference database and a separate fresh faulty database. The baseline must match the independently authored expectation before the faulty observation counts as detected. The results are saved in `artifacts/workflow-benchmark.json` with WF rule IDs and the workflow contract hash.

Together with V1's seven retained evaluation seeds, V2 demonstrates twelve specific defect detections. This is not an exhaustive mutation score or a blind benchmark. The variants were authored with knowledge of the contracts and tests. Their value is concrete evidence that selected assertions can distinguish a defined business risk from the reference behavior.

The rollback and concurrency checks are separate tests, not additional mutation seeds counted in that twelve. Keeping these categories distinct avoids inflating a benchmark result with unrelated checks.

## 15 The actual AI review and how its output was judged

V2 used the already installed local model `qwen2.5-coder:3b` through Ollama. It reviewed the synthetic HC/WF contracts, not application code, stored claims or the test suite. The response reported 2490 input tokens, 262 output tokens and approximately 7.09 seconds of request latency. The request used temperature 0, an 8192-token context setting and a 1000-token output budget.

The model suggested an unknown-actor 403 check, duplicate-claim 409 check and repeated-approval conflict check. Those are reasonable assertions. However, each accompanying observation claimed the relevant behavior was not explicitly defined. WF-001, WF-002 and WF-003 already define those behaviors, and the suite already contained corresponding tests before the review was assessed.

I preserved the raw output in `artifacts/v2/ai-review.json` and wrote an engineering assessment beside it. No suggestion was counted as a new contribution or automatically turned into an executable test. This is a useful learning result: a plausible test idea can still come with an unsupported claim about the specification or test coverage.

The assessment was performed by Codex against the contracts and executed tests. Your learner review remains pending; the artifact does not falsely record human approval. The earlier V1 review used a different model and task, so the two runs do not establish that one model is better. A controlled comparison would require the same inputs, scoring and repeated evaluation.

Codex and Ollama were actually used in this version. ChatGPT, Copilot and Claude Code have prepared exercises, not claimed executions. The optional review script validates response structure and rule IDs, has bounded output and timeout behavior, and never executes suggestions. Structured AI-generated proposals with approval remain V3.

## 16 What was shown in VS Code and how to use it

The V2 implementation plan and `healthcare_quality/workflow.py` were opened in the Healthcare Quality Lab VS Code window. The visible editor state confirmed that the workflow implementation was displayed. The detailed report will also be opened there for inspection.

Project tasks and debug labels now identify V2. The application launch uses port 8892, while the first deductible-test debugger remains available. Tasks provide full verification, smoke, sanity, visible browser automation, the evaluation benchmark, workflow benchmark and local coding-model review.

VS Code was observed in Restricted Mode. I did not change folder trust or other security preferences. You can inspect the code and decide whether to trust this folder; terminal verification works independently of the editor trust setting. No global editor configuration or unrelated workspace was changed.

The GitHub Actions definition now labels its artifacts as V2 and invokes the expanded verification runner. It remains a locally prepared workflow. No remote repository was created or pushed, no GitHub run was observed, and no deployment occurred.

## 17 Implementation findings and design tradeoffs

The first stateful test run exposed an insert statement whose number of values did not match the table shape. I corrected it by listing the ten target columns explicitly. This is one reason the HTTP service is not considered verified merely because it starts: a real submission test must exercise storage.

The expanded interface also made a retained browser locator ambiguous: Authorization received matched both the evaluation checkbox and the new workflow checkbox. I made the retained test's locator exact, preserving its original assertion. The new page object centralizes workflow selectors so similar interface maintenance is easier to manage.

Final visual QA also caught a report renderer that applied the version label to body text, incorrectly changing historical V1 references into V2. The correction now changes only report chrome, and two parametrized regression cases preserve the original comparison text for both output versions. This demonstrates why inspecting the rendered report matters in addition to checking that its route returns 200.

SQLite and a single local service were chosen instead of adding a cloud database or multiple services. This gives us real transaction behavior without operational setup that would obscure the lesson. It also limits the scope: there is no schema migration system, distributed coordination, queue, worker or production identity provider.

The workflow hashes fixture definitions and stores the evaluated snapshot. That supports evidence comparison across future code changes. It does not implement re-adjudication against newly edited policy files. The system records what was evaluated at submission; changing an evaluation afterward would need a new explicit contract.

## 18 What V2 achieved and what it does not establish

V2 achieved the planned stateful foundation: owned synthetic submissions, duplicate protection, ordered lifecycle, role restrictions, a unique simulated ledger, persistent evidence, isolated tests and reusable testing components. It demonstrates that rejected actions leave state unchanged and that tested storage failures do not partially commit.

You can now show more than a passing payout calculation. You can explain why a coverage-approved request is still submitted, who may move it forward, what a transaction protects, why duplicate requests conflict, and which evidence records prove the observed sequence. Those explanations are the learning outcome the code is meant to support.

The member fixtures are not real eligibility records. The actor selector is not authentication. The ledger is not a payment system. The history is not an immutable audit log, and failed attempts are not persisted as security-audit events. Anyone able to edit the local files or database can change them.

All V1 coverage limitations remain: no actual plan adjudication, negotiated allowed amounts, annual accumulators, coordination of benefits, clinical rules, coding standards, appeals, or payer integrations. V2 also has no cancellation/reversal workflow, optimistic client revision token, pagination, database migrations or stress-tested throughput. The concurrency evidence covers two local threads, not a production system.

No new paid AI account or cloud service was configured, and no real patient or member information was introduced. The successful tests support the implemented synthetic contracts on the recorded environment; they do not certify regulatory compliance or real-world insurance correctness.

## 19 Reproduce the workflow and inspect the files

Open only `/Users/erdalkilic/Documents/Healthcare Quality Lab` in VS Code. From its terminal:

```sh
source .venv/bin/activate
python -m tools.verify
python -m flask --app healthcare_quality.app:create_app run --host 127.0.0.1 --port 8892
```

Open `http://127.0.0.1:8892/#workflow`. Select Customer / M100, generate an unused claim ID, keep Medical and 100000 cents, then submit. Inspect submitted / revision 1. Switch to Adjuster / demo and approve. Switch to Finance / demo and record the simulated payment. Inspect paid / revision 3 and export the workflow JSON.

To reproduce a denial, use Customer / M200 with Hospital and missing authorization. Correct the flag and reuse the rejected ID. To observe duplicate protection, reuse a successfully submitted ID. To watch browser automation, run `python -m pytest -m e2e --headed --slowmo 350 -v`. Tests provide their own servers and databases; the interactive server need not be running.

| File or directory | Why it exists |
| --- | --- |
| healthcare_quality/workflow.py | Transaction store, role/ownership checks, submission, transitions and evidence |
| healthcare_quality/data/members.json | Nine synthetic member/policy fixtures |
| healthcare_quality/data/actors.json | Twelve named demo identities and role/member associations |
| healthcare_quality/data/workflow_rules.json | Six exact stateful requirements and risks |
| healthcare_quality/app.py | Current HTTP contracts, error responses and report routes |
| healthcare_quality/static/workflow.js | Workflow desk interactions and stale-view response handling |
| tests/support/api_client.py | Reusable API request vocabulary |
| tests/support/workflow_page.py | Reusable Playwright actions and selectors |
| tests/unit/test_workflow.py | Lifecycle, rejection, persistence, rollback and concurrency assertions |
| tests/api/test_workflow_api.py | HTTP workflow and ownership checks |
| tests/e2e/test_workflow_browser.py | Real browser workflow scenarios |
| tests/data/workflow-traceability.json | Explicit WF rule-to-test links |
| tools/workflow_benchmark.py | Five controlled stateful fault experiments |
| artifacts/v2/ | Version-specific AI review and final copied evidence |
| docs/V2_DEMO.md and LESSON_02.md | Guided demonstration and learning explanation |

The database files created by the interactive app are separate from source snapshots. There is no reset endpoint that deletes saved claims. Use temporary test fixtures when an experiment requires a fresh store.

## 20 How V2 prepares V3 and the next learning step

V3 will use these stable workflow actions as the boundary for AI-generated test proposals. A model will need to cite a contract, describe safe inputs and expected outcomes, pass validation, and obtain explicit reviewer approval before controlled execution. V2 does not grant a model direct database access, arbitrary Python execution or automatic permission to approve claims.

V4 remains the evaluation and investigation milestone, including reviewed/held-out examples and grounded failure explanations. V5 remains the release and showcase milestone, including actual remote CI and a chosen deployment/rollback path. The complete roadmap remains in `docs/ROADMAP.md`; this delivery stops at V2.

For your own learning, read `docs/LESSON_02.md` and explain what must remain unchanged after a failed payment. Then run one focused rollback test and compare its before/after evidence. Finally, read the local model's three suggestions and identify the exact contract sentence that contradicts each claim of an unspecified rule.

The outcome is a broader framework you can inspect, run and challenge: reliable software behavior first, then AI assistance evaluated against explicit evidence.
