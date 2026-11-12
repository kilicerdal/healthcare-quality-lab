# Healthcare Quality Lab V3 Engineering Report

**Version:** 3.0.0 — Local AI test creation

**Implementation date:** November 11, 2026, America/New_York

**Project location:** `/Users/erdalkilic/Documents/Healthcare Quality Lab`

**Outcome:** V3 now uses real local Ollama inference to create new structured test cases from a requirement. The AI Test Studio saves proposals and provenance, validates permitted actions, supports reviewed corrections, requires explicit approval, executes only approved snapshots in disposable databases, and exports reviewed cases as trusted pytest wrappers. The deterministic regression suite passed 258 cases. Real model errors, reviewer corrections and live execution evidence are recorded separately.

## 1 Why we built V3

V1 gave us written synthetic coverage rules and independent tests. V2 added claim ownership, persistence, duplicate handling, an ordered lifecycle and a simulated payment ledger. Those versions created a system whose behavior we can inspect and challenge. V3 uses that system as the target for AI-created tests.

The purpose is to learn the complete process from an English testing goal to a reviewed, executable test case. We want the model to help propose scenarios and assertions while keeping correctness decisions inspectable. The framework must not confuse an impressive-looking answer with a reliable test oracle.

The actual local models demonstrated why this distinction matters. They created plausible cases but also proposed an incorrect payout, attached workflow observations to a stateless evaluation, used quoted amounts, supplied prose instead of a reason code and omitted requested monetary/history checks. A useful framework must preserve and expose those findings rather than hide them behind a passing badge.

V3 therefore delivers both generation and controls: structured output, independent validation, visible sources, editable expected results, explicit review decisions, revision/hash checks, isolated execution and expected-versus-observed evidence. It does not claim autonomous testing correctness or eliminate the need for a knowledgeable reviewer.

## 2 Where the work happened and what stayed separate

All V3 implementation changes were made inside the standalone Healthcare Quality Lab directory. No neighboring Generative AI framework, Insurance claim framework or other project was used, moved or modified. Temporary authoring and acceptance scripts were staged in `/private/tmp`; the application does not depend on those scripts.

Before starting, I verified the preserved V2 source archive against its SHA-256 manifest. V1 and V2 source snapshots, reports and version-specific evidence remain available. `/report` now serves V3, while `/reports/v1` and `/reports/v2` serve the historical reports. A version is a milestone in this project, not a new folder inside an unrelated project.

The V2 interactive workflow tables remain in `.local/claims-v2.sqlite`; the legacy filename is retained because those tables were not migrated. AI experiment metadata is separate in `.local/ai-v3.sqlite`. Both are runtime data excluded from source snapshots and Git tracking. Automated and live acceptance tests use dedicated temporary stores and do not create test claims in the interactive workflow database.

The original real workflow proposals saved in the interactive AI store remain unapproved for your own review. Engineering demonstrations used disposable copies and explicit engineering-review labels. Those records do not falsely represent a completed learner approval.

## 3 What V3 adds to V2

| Area | V2 | V3 |
| --- | --- | --- |
| Local AI capability | Optional text review of contracts | New structured test cases generated from a requirement |
| Model output | Suggestions for manual reading | Cases with source IDs, rationale, assumptions, actions, inputs and expected observations |
| Validation | Review-script response checks | JSON Schema, action fields, source selections, duplicates, observable fields and quality warnings |
| Review | Engineering assessment in files | Editable cases, reviewer notes, explicit attestation and selected-case approval |
| Version control inside an experiment | Raw review artifact | Revisions, before/after corrections, approval hashes and run snapshots |
| Execution | Authored regression tests | Controlled execution of explicitly approved generated case data |
| Python test artifact | Handwritten pytest suite | Downloadable trusted parametrized wrapper containing reviewed AI case data |
| UI | Evaluator and workflow desk | AI Test Studio with generation, review, execution and evidence views |
| Recorded core regression | 184 passing cases, 16 browser checks | 258 passing cases, 23 browser checks |

The original synthetic application and twelve authored evaluation/workflow defect experiments remain. AI-generated cases do not replace the independent reference suite.

## 4 What AI actually creates

Ollama creates new case objects. It does not select a case ID from `tests/data/golden.json`, and that golden dataset is not supplied to the generator. A case contains an AI-prefixed identifier, title, cited rule IDs, rationale, proposed assumptions and an ordered sequence of steps.

Each step declares an action, actor, data and expect. The model chooses the scenario structure and expected observations within the permitted language. For example, the actual workflow generation created a submission using a new claim ID, a repeated submission expecting DUPLICATE_CLAIM, and a read expecting the original submitted state and revision.

The executable part is a small declarative language, not model-authored Python. Python interprets four known actions: evaluate, submit, transition and read. This gives us a usable test artifact while avoiding a shortcut in which arbitrary model code receives access to the developer's machine.

Expected values are still proposals. A model can produce valid JSON and cite a real rule while calculating a payout incorrectly or checking too little. The review and evidence stages exist to make those mistakes visible.

## 5 The end-to-end architecture

The flow is: requirement and selected sources → exact prompt and schema → local Ollama → saved raw response → validation findings → reviewer edits/attestation → approved snapshot → isolated runner → evidence and pytest export.

`ai_schema.py` defines the case language, action-specific shapes, bounded fields, expected observables and validation/quality checks. `ollama_provider.py` owns the fixed local endpoint and request/response limits. `ai_studio.py` persists experiments, handles edits/reviews and gates execution/export. `ai_runner.py` maps known actions onto the existing Python services in fresh databases.

Flask exposes those components through JSON routes. The browser studio lets you brief the model, inspect drafts, edit JSON, approve selections and read execution evidence. It is a user interface over the same server-side checks; disabling a browser button is not the approval mechanism.

The original evaluator and workflow service remain the system under test. The generator does not decide their behavior. The runner records what those services actually returned and compares only the explicitly approved assertions. A mismatch is an observation, not automatic proof of a product defect.

## 6 Local Ollama integration and operational bounds

V3 sends generation requests only to `http://127.0.0.1:11434/api/generate`. The allowed model tags are the already installed `qwen2.5-coder:3b` and `qwen2.5:3b`. It does not pull a model, choose a cloud provider or substitute fixture output if inference fails. Check Ollama reads the local model list and reports availability.

The provider passes a JSON schema in the format field and also includes the schema in the prompt. This follows the mechanism documented by Ollama's [structured output guide](https://docs.ollama.com/capabilities/structured-outputs) and [generation API](https://docs.ollama.com/api/generate). The application validates the result again; schema-guided sampling is not treated as sufficient verification.

Each request uses temperature 0, seed 7, a 2600-token output setting, a 12288-token context setting, non-streaming output and a 90-second timeout. The response envelope is capped at 256 KiB. One generation is allowed at a time per studio service instance. Provider errors, incomplete output and exhausted output budgets are saved as explicit failures.

These are operational controls, not proof of deterministic model behavior. The exact prompt, settings, response and reported token counts are retained, but a model tag can later point to different weights. V3 does not capture a weight digest in every generation record or promise bit-for-bit reproducibility across machines.

## 7 Source context and what grounding means here

A generation request selects one to six existing HC/WF contracts. The prompt includes their exact text, the synthetic plans and member/actor fixtures, the action interface and the user requirement. The saved experiment retains the selected rule text and exact prompt, so the reviewer can see the context behind a proposal.

The validator checks that cited IDs exist and were selected. Workflow actions must cite a WF contract; evaluation must cite an HC contract. This prevents invented or unselected source identifiers from passing unnoticed.

It does not establish that a citation semantically justifies every expected value. Nor does V3 search arbitrary documents, build embeddings or implement vector retrieval. Sources are explicit user selections from the controlled synthetic rule library. Broader retrieval quality and evaluation belong to V4.

The user requirement is framed as task data that cannot change the schema, permitted actions or review rules. That instruction alone is not a prompt-injection defense. The effective execution boundary is the server's constrained language and lack of model tool access.

## 8 Validation controls and their limits

A case must match JSON Schema: known properties, supported action variants, bounded strings/amounts, typed inputs, explicit expected observations and a limited number of steps. Additional code/command fields and unsupported action names are rejected. Evaluation cases cannot request workflow event observations, and expected reason/error values must be known codes.

Server checks also cover unique case IDs, duplicate action/expectation sequences, selected sources, action-specific fields, expected integer types and observable names. Every case needs status plus at least one business assertion. Invalid cases remain inspectable but cannot be approved.

Quality warnings expose proposed assumptions and some missing oracle fields. For example, a case citing WF-004 without payment_cents receives a missing-payment-assertion warning. These checks help review; they are not a complete coverage or semantic-quality evaluator.

The initial DSL supports typed bounded action inputs. Arbitrary malformed-type requests are not all expressible in generated cases; the independent pytest suite still covers those payload errors. A reviewer must also judge requirement coverage, precedence, assumptions and arithmetic. Validation does not make the model's oracle correct.

## 9 Persistence, provenance and experiment states

AI metadata is stored in a separate SQLite experiment table. The record includes requirement, model, strategy, selected sources, exact prompt/hash, settings, schema/contract fingerprint, raw generation, validation findings, current cases, revision, review history, approved IDs and recorded runs.

An experiment starts generating, then becomes proposed or generation_failed. Proposed output contains no approval and no run. Review may approve selected valid cases or record a review with no cases approved. During execution, the experiment is running; an ordinary completed or failed run is recorded and the approved state is restored for a deliberate rerun.

Edits preserve the previous case and the corrected case in history. Raw model output is retained separately and is not rewritten to look correct. Review decisions also advance the revision. Optimistic revision checks reject stale edits, reviews and execution requests.

Local JSON records, SQLite rows and hashes are provenance aids, not tamper-proof signatures. Someone with local file/database access can alter them. An abrupt process exit can leave a generating/running record; automatic crash recovery, retention quotas and administrative recovery controls are not implemented in V3.

## 10 The review gate and why edits invalidate approval

The reviewer selects valid cases and supplies a label, explanatory note and explicit attestation that sources, inputs and expected results were checked. Saving with no selected cases records no approval. A nonempty approved selection stores the exact case hashes and current revision.

Editing any case clears the previous approval, even if the edit looks small. The reviewer approved one data snapshot; changing an amount or expected value creates a different test. Both execution and pytest export revalidate the cases and compare their hashes with the saved approval.

The contract/schema fingerprint must also match the current framework. Historical development generations with an older schema are visible but cannot be approved as current proposals. The studio labels those records and asks for a new generation rather than silently reinterpreting them.

Reviewer labels are local attestations, not authenticated human identity. V3 cannot establish that a person understood the test just because a checkbox was selected. The delivered live demonstrations explicitly identify Codex engineering review and leave your original saved workflow proposals unapproved.

## 11 How generated cases execute

The runner permits only evaluate, submit, transition and read. It never evaluates generated Python, invokes a shell, follows a generated URL or grants direct database access. Each case receives a new temporary SQLite file; ordered steps inside that case share state, while another case starts clean.

The budget is four cases with up to eight steps each, for at most 32 actions. A ten-second elapsed-time check is made between actions; this is not a hard process-level kill. The runner stops a case at its first failed assertion so later actions do not obscure the first mismatch. Other cases may continue within the bounded run.

Generated cases call the existing Python services directly. Their status observations are service/error projections corresponding to the documented HTTP semantics; they are not actual HTTP transport tests or generated browser automation. Separate authored API and Playwright tests verify those application boundaries.

The run records approved case data, reviewer attestation, model/prompt identifiers, source hash, every expected/observed comparison and full service evidence. Temporary execution files are removed on normal completion and ordinary Python exception cleanup. No generated run uses the interactive claim database.

## 12 The trusted pytest export

After approval, the studio can download a parametrized Python test wrapper. The wrapper is fixed application-authored code. The model-created material inside it is safely encoded JSON data containing the reviewed cases and approval metadata; the model does not author the executable wrapper.

Before running, the wrapper checks contract/schema compatibility, the case hash and case validity. It then invokes the same isolated runner and reports failures with detailed evidence. Each selected case becomes a pytest parameter.

An integration test actually writes the exported wrapper to a temporary file and runs pytest on it. The two reviewed live workflow cases were also exported and executed separately, with two passing cases. Those exported runs are not added to the core regression count as if they were new independent tests.

To use your own download, save it under this project's tests/generated directory and run pytest. If the contract/schema later changes, the snapshot check requires review again. The wrapper does not authenticate the identity or integrity of a file edited by a local user.

## 13 What the real local models produced

Six live generation requests were exercised during development and acceptance: five two-case requests through the provider/service path, and one single-case request through the actual browser form. Together they produced eleven draft cases. The requests used different evolving prompts/schemas and two local models; this is not a controlled model-quality comparison.

The first output added event_count to stateless evaluations, so both cases were blocked. It also proposed a 50000-cent payout for a 150000-cent claim, contradicting the 10000-cent deductible. The raw output was preserved and the action-specific grammar was tightened.

A later output quoted monetary inputs and confused a claim amount with the payout cap. Another supplied explanatory prose in a reason-code field and omitted the payout assertion. These observations led to typed generation inputs, bounded reason/error codes and visible missing-oracle warnings. Earlier schema fingerprints remain distinguishable from the final one.

The final workflow generation created two usable action sequences: duplicate submission and a complete approval/payment lifecycle. Its status/revision expectations were correct, but it omitted the requested event counts and simulated payment amount. That gap was documented rather than concealed by their passing narrow assertions.

Every provider attempt is preserved by experiment ID under artifacts/v3. Some convenience filenames represent the latest attempt for that brief; the generation-ID files preserve each distinct request. The six-request count includes the separate browser acceptance artifact.

## 14 The engineering-reviewed live workflow demonstration

I copied the final real workflow experiment into a disposable metadata store. Before approval, execution was rejected with REVIEW_REQUIRED. An explicitly labeled engineering attestation then approved only the raw cases' narrow stated expectations. Both cases passed across seven actions.

Next, I added independent payout, payment and event-count assertions from HC-007 and WF-004/005. For a 100000-cent claim, payout is 90000; successful event counts are 1, 2 and 3; payment is absent until paid and then equals 90000. The generated workflow actions and original raw response were retained.

The edit invalidated approval, and an attempted run was blocked again. After a new engineering review, both strengthened cases passed. Their trusted pytest export also passed two parametrized cases. These are repeated executions of two cases and revised oracles, not six different independent AI discoveries.

The evidence is in live-demo-experiment.json and live-demo-summary.json. The review label says Codex engineering demo — not learner approval. The original interactive experiment still has no approval or runs, ready for your own inspection.

## 15 The actual browser-to-Ollama acceptance run

A separate temporary application used the real local provider, not a fixture. The browser selected the model, checked Ollama availability, submitted a one-step brief, received the real response, saved a correction, recorded review and executed the approved snapshot.

The acceptance brief explicitly supplied a 45000-cent claim and 35000-cent expected payout. This was an integration smoke brief with reference values, not an independent reasoning benchmark. The model returned the correct input and status/decision/reason but omitted payout_cents despite the brief. The engineering review added that missing assertion before approval.

The corrected case passed with expected and observed payout both 35000. The temporary interactive workflow store remained empty. Desktop/mobile screenshots were inspected, horizontal overflow was checked at a 390 × 844 viewport, and no JavaScript page errors were observed.

The run reported 3178 input tokens and 185 output tokens. Its exact raw response and before/after correction are preserved in browser-live-generation.json, browser-live-experiment.json and browser-live-summary.json. This experiment was engineering-reviewed in a disposable metadata store; it does not represent your personal sign-off.

## 16 The final deterministic verification results

The final recorded regression completed at 2026-11-11T22:57:39.652508-05:00 using python -m tools.verify.

| Evidence | Result |
| --- | --- |
| Core regression cases | 258 passed, 0 failed, 0 skipped |
| Unit cases | 190 passed |
| API cases | 45 passed |
| Chromium browser cases | 23 passed |
| Smoke selection | Nine cases across unit, API and browser boundaries |
| Sanity selection | Nine focused cases including review-gate and approval-invalidation checks |
| Retained evaluation fault seeds | 7 out of 7 detected |
| Retained workflow fault seeds | 5 out of 5 detected |
| Original golden business examples | 28 reference examples without mismatch |
| Separately exported live workflow cases | 2 passed, outside the core count |
| Live browser acceptance | 1 reviewed case passed, outside the core count |
| Regression duration | 24.57 seconds on the verified environment |
| Live inference inside the core suite | No; explicitly named offline provider doubles |
| Remote GitHub Actions execution | Not performed |

The source SHA-256 is `304c61620988e7c37fb6cad30d223ced09a7035db62e227908c266b2e343025b`. Python 3.13.18, pytest 8.4.2, Playwright 1.56.0 and Flask 3.1.2 were used; V3 adds pinned jsonschema 4.25.1. Core provider doubles are isolated test dependencies, never an application fallback when Ollama fails.

New checks cover unsafe/unsupported output, weak oracles, duplicates, source selection, provider limits, missing attestation, partial approvals, no approval, stale revisions/contracts, changed case hashes, edit invalidation, concurrent execution, execution exceptions, store persistence, temporary-file cleanup, exported wrappers and studio browser flows.

A larger test count is not an exhaustive coverage score. No full accessibility audit, security certification, performance benchmark, held-out AI evaluation or generated-browser-test capability is claimed.

## 17 What was shown in VS Code and daily workflow

The V3 plan and generation/review modules were opened in the Healthcare Quality Lab VS Code window. The observed editor title confirmed ai_studio.py was displayed, with the schema module also open. The detailed V3 report is provided as editable Markdown and printable HTML.

Tasks and launch labels now identify V3 and use port 8893. The AI marker selects generation/review/runner tests; smoke, sanity, full verification and visible browser tasks remain available. The original evaluator and lifecycle tabs remain usable beside the new studio.

VS Code's folder trust setting was not changed automatically. If the editor is in Restricted Mode, inspect the code and decide whether to trust this standalone folder. The verified terminal commands work independently of that preference.

The GitHub Actions definition is updated to V3 and retains deterministic provider doubles rather than requiring Ollama on a hosted runner. It is prepared locally only. No remote repository, paid model account, deployment or CD run was configured.

## 18 Acceptance criteria, limits and remaining risks

V3 met its implemented acceptance criteria: real Ollama created case proposals; invalid output was inspectable and blocked; no generation executed a test; selected cases required explicit attestation; edits invalidated approval; hashes/contracts/revisions gated runs and export; isolated execution produced evidence; reviewed cases ran through pytest; and the full regression passed.

The gate is a local workflow control, not production identity or a guarantee of human review quality. A reviewer can still approve an incorrect oracle, and the runner can only compare the assertions it receives. Source-ID checks and quality warnings are limited static checks, not complete semantic validation.

The DSL does not express every possible malformed request, arbitrary test fixture, assertion type, browser interaction or external integration. The generated runner uses Python services and HTTP-equivalent projections, not actual HTTP requests. Real payer behavior, real benefits, PHI, clinical rules and real payments remain outside the synthetic application.

The output budget and action bounds reduce operational risk, but the runner deadline is cooperative between actions. Automatic recovery after an abrupt process exit, multi-process global generation limits, storage quotas, immutable audit logs and authenticated reviewer identity remain future work. Local histories/hashes can be changed by a local operator.

The local 3B models made meaningful mistakes. The six requests differ across development schemas/prompts, so they establish integration behavior and observed error examples, not general model accuracy, model superiority or statistical confidence. Exact weight digests and cross-machine deterministic replay are not guaranteed.

## 19 How to use and inspect the delivered version

Open only `/Users/erdalkilic/Documents/Healthcare Quality Lab`. Select its .venv/bin/python interpreter. Start the server:

```sh
source .venv/bin/activate
python -m flask --app healthcare_quality.app:create_app run --host 127.0.0.1 --port 8893
```

Open http://127.0.0.1:8893/#ai. Check Ollama, describe a synthetic requirement, select relevant sources and generate. Read the proposal and warnings. For workflows, include the WF sources you expect to cite; edits cannot add a rule that was not selected for the experiment.

Fill a reviewer label and explanatory note. Save any JSON correction, select valid cases, attest that expectations were checked and save the review. Run only the approved snapshot and inspect every mismatch. Checkbox changes alone do not change saved approval; save the new decision before expecting a different selection to run.

Export the experiment JSON for provenance. Export the approved pytest wrapper for Python execution. The delivered live wrapper can be rerun separately:

```sh
python -m pytest -c pytest.ini artifacts/v3/test_ai_generated_live.py -q
```

| Location | Purpose |
| --- | --- |
| healthcare_quality/ai_schema.py | Declarative format, validation, fingerprints and quality warnings |
| healthcare_quality/ollama_provider.py | Fixed local provider and request/output limits |
| healthcare_quality/ai_studio.py | Versioned proposals, corrections, attestation, approval and runs |
| healthcare_quality/ai_runner.py | Permitted-action execution in disposable databases |
| healthcare_quality/static/ai-studio.js | Browser generation, review, evidence and downloads |
| tests/unit/test_ai_studio.py | Approval, revision, validation, isolation and export controls |
| tests/unit/test_ollama_provider.py | Provider contract, error and size checks |
| tests/api/test_ai_api.py | HTTP generation/review/execution boundaries |
| tests/e2e/test_ai_browser.py | Studio user workflows with explicit provider doubles |
| artifacts/v3/ | Raw real generations, corrections, live runs and version evidence |
| docs/V3_CONTROLS.md | Exact control scope and acceptance behavior |
| docs/LESSON_03.md and V3_DEMO.md | Guided learning and demonstration |

Fresh-machine setup is in the README. Model installation and starting Ollama are explicit prerequisites; the app does not silently download a model. Historical reports and source archives remain available for comparison.

## 20 What we achieved and how V4 follows

You now have AI creating actual test-case proposals with local Ollama, a visible way to review and correct them, controlled execution against the synthetic application and a Python pytest artifact. The project records both useful model output and its errors instead of presenting all generated material as correct.

The learning outcome is the ability to explain the difference between generation, validation, review and evidence. Read an actual case, identify its oracle, check the arithmetic or lifecycle rule, look for missing assertions, and explain why a narrow passing test may still leave a requirement untested.

V4 remains the next planned version: broader reviewed/held-out evaluation data, prompt experiments, grounded failure investigation and useful quality metrics. V5 remains release packaging, actual remote CI and a chosen deployment/rollback workflow. Those capabilities are not presented as delivered in V3.

The detailed evidence supports a concrete claim: local AI is now part of the test-creation workflow, with explicit limits and reviewable outcomes. It does not support replacing engineering judgment with model confidence.
