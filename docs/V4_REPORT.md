# Healthcare Quality Lab V4 Engineering Report

## 1. What we achieved

V4 adds a working AI Quality Lab to the standalone healthcare testing project. It measures local AI test proposals against explicit reference expectations, compares two prompt strategies under the same conditions, retrieves written source contracts, and investigates recorded failures with local Ollama. You can inspect these features in the browser and read their Python implementation in VS Code.

The key achievement is the ability to distinguish a well-formed test from a useful test. Our actual local model produced valid case structures while omitting financial and history assertions and sometimes proposing the wrong expected payout. V4 made those defects visible instead of turning them into a misleading success score.

Final deterministic verification: **297 tests passed, zero failed, zero skipped**. This includes **222 unit, 48 API and 27 real Chromium browser tests**. The retained engineering fault experiments detected **7 of 7 evaluator faults and 5 of 5 workflow faults**. These finite examples do not establish exhaustive correctness.

The separate live AI experiment made **16 real local Ollama generation requests**, producing one draft per request, and one additional real failure-explanation request. All 16 comparison drafts remain unapproved and unexecuted. A deliberately authored wrong-oracle fixture was separately reviewed with an explicit engineering label and executed to create the failure evidence. It was never described as an Ollama-generated test.

## 2. Where this was built and what was preserved

All implementation work belongs to `/Users/erdalkilic/Documents/Healthcare Quality Lab`, a standalone folder directly under Documents. V4 did not use your Generative AI, Insurance claim framework, or website projects as dependencies or destinations.

V1, V2 and V3 remain preserved in versioned source archives, manifests, reports and evidence directories. The live application is now version 4.0.0. Updating its current code is how this single project evolves; the release archives preserve earlier implementations. Historical report pages remain available at `/reports/v1`, `/reports/v2` and `/reports/v3`. The current report is `/reports/v4` or `/report`.

The V3 archive checksum was verified before implementation. Existing browser tests initially still expected the V3 title and used V3 screenshot names; I updated current-version expectations and screenshot destinations, and restored the historical screenshot copies from the preserved V3 archive. The final checks passed with the V4 destinations.

Application state stays in project-local SQLite files. Interactive claims use `.local/claims-v2.sqlite`; the existing Studio uses `.local/ai-v3.sqlite`; V4 comparisons and investigations use `.local/evaluation-v4.sqlite`. Test fixtures use temporary databases. Model-generated case execution still creates a fresh disposable database for every reviewed case.

## 3. Why V4 exists

V1 established written synthetic contracts and deterministic testing. V2 added persisted claims, ownership, approval, simulated payment and transaction history. V3 made local AI create new declarative test proposals and introduced validation, editing, explicit review and isolated execution.

V3 left an important learning question: how do we know a generated test is meaningful? A test can pass because it checks only a status code while ignoring an incorrect payment. A model can confidently write an incorrect expected value. A longer prompt can sound more careful while producing worse cases. Merely counting generated tests cannot answer these questions.

V4 therefore measures the quality of the proposals and the strength of their assertions. It also demonstrates a disciplined failure-investigation workflow: extract what actually happened, find the applicable written rules, then request a bounded explanation. The explanation cannot replace the observed facts.

## 4. What you can see in the application

Open `http://127.0.0.1:8894/#evaluation` and select **AI Quality Lab · V4**. The workbench has four connected areas.

- A comparison form selects the development or reserved split, a local model and up to four task briefs. It compares balanced-v1 and oracle-check-v2, with one generated case for each task and strategy.
- Saved evidence shows progress, exact count denominators, each task's missing or incorrect assertions, and a complete JSON download. Every generated draft also remains available in AI Test Studio.
- Rule retrieval accepts a rule ID or keywords and displays ranked source contracts, matched terms and explicit scores.
- Investigation selects an actual saved Studio execution. The model explains failed assertions using evidence IDs and source IDs; successful runs abstain without making a model request.

The existing claims explorer, coverage library, rulebook, workflow desk and AI Test Studio remain available. V4 adds a measurement and investigation layer around those functions rather than replacing them.

## 5. Language, framework and architecture

Python remains the main language. Flask serves the local web application and JSON APIs. pytest runs the unit, API and browser suites. Playwright Python drives real Chromium browser interactions through pytest. SQLite persists synthetic claim and experiment records. Browser presentation uses the existing HTML, CSS and JavaScript interface.

`healthcare_quality/evaluation.py` loads the reference dataset, normalizes case inputs, compares explicit expectations and retrieves contracts. `healthcare_quality/quality_lab.py` manages comparison jobs, freezes their prompts, stores progress and extracts investigation evidence. `healthcare_quality/app.py` exposes the new endpoints. `static/evaluation.js` connects those endpoints to the workbench.

`tools/v4_live.py` is an explicit opt-in runner for live development, reserved, investigation and sensitivity experiments. It is outside default pytest collection. `tools/assertion_sensitivity.py` replays already reviewed historical snapshots against two known workflow faults. Their internal fault controls are application-authored engineering tools; the public generated-test language cannot select a fault or run arbitrary code.

The data flow is: authored task brief and selected contracts → frozen prompt → local Ollama proposal → structural validation → reference comparison → saved evidence. No arrow in this comparison flow approves or executes the proposal.

## 6. The eight-task evaluation dataset

The versioned file is `healthcare_quality/data/evaluation_v4.json`, version 4.0.0-dataset-1. It contains four development tasks and four reserved tasks, literal reference expectations, required assertions, source IDs and the derivation of each reference.

| ID | Split | Scenario | Why it matters |
| --- | --- | --- | --- |
| D01 | Development | PPO medical claim, 48,500 cents | Deductible arithmetic must yield 38,500 cents |
| D02 | Development | PPO medical claim, 7,600 cents | Below the 10,000-cent deductible, approved payout is zero |
| D03 | Development | Duplicate submission and readback | A rejected duplicate must not add history or a payment |
| D04 | Development | Another member attempts to read a claim | Ownership must be enforced across reads |
| H01 | Reserved | 278,900-cent claim | The synthetic payout cap is 200,000 cents |
| H02 | Reserved | 200,000-cent claim | Claim amount equal to the cap still subtracts the deductible: 190,000 |
| H03 | Reserved | Submit, approve, pay and read | Lifecycle, revision, history and ledger must agree |
| H04 | Reserved | Finance attempts payment before approval | Rejection must leave status, revision, events and payment unchanged |

The reference cases were authored from the synthetic contracts and independently expressed as literal expectations. Automated engineering checks validate their structure and confirm that observed application behavior agrees with them. Agreement with the application is supporting evidence, not an independent certification of the application. You have not yet personally reviewed or certified this dataset.

The reserved tasks were kept out of prompt tuning during this delivery. They are not unknown to their author, and the application exposes the references for learning. The first held-out use exposes answers; subsequent jobs are labeled reused. This is a small educational evaluation set, not an external benchmark or statistically representative healthcare corpus.

## 7. How scoring works and why it does not run drafts

V4 compares a model's draft data with the authored reference data. It does not execute the model's proposed actions. Execution remains subject to V3's explicit review and hash-bound approval gate.

The scorer first requires exactly one structurally valid proposal. It then checks the action sequence, actors and input values. Claim IDs are normalized consistently within each case, so a harmless identifier change can match; using a different ID for the final read cannot. Omitted optional flags are normalized to their documented true defaults.

The scorer only compares expectation values when the requested inputs and sequence match. A different valid scenario is labeled unmatched, with zero comparable assertions. It is not automatically declared an incorrect alternative test.

| Measurement | Meaning | Denominator |
| --- | --- | --- |
| Generation succeeded | A proposal envelope was returned and parsed | Model requests recorded |
| Schema valid | Case structure, sources and types satisfy the validator | Requests recorded |
| Input match | Exact brief inputs, actors and sequence match after normalization | Requests recorded |
| Required assertions present | Requested reference fields appear in the draft | Required fields for that task |
| Required assertions correct | Those fields have the exact expected type and value | Required fields for that task |
| Comparable assertions correct | Declared fields that the reference can compare are correct | Comparable declared fields only |
| Strict task pass | All required fields are correct, with no missing, contradictory or unscored extra fields | Requests recorded |

These measures deliberately stay separate. A 100% correctness result among declared comparable fields can coexist with missing payout assertions. Unsupported extra observations prevent a strict pass but are not silently treated as proven correct. For H04, the model added a revision expectation to a rejected transition where the reference did not establish that observation; it was recorded as an unscored extra.

## 8. Controlled prompt comparisons

balanced-v1 asks for distinct relevant scenarios. oracle-check-v2 adds an instruction to follow exact inputs and action order, calculate expectations independently and include requested money, revision, history and ledger checks. It adds no task-specific reference answers.

Before the first request in each job, the system persists the complete prompts, prompt hashes, task/reference snapshots, dataset version and hash, model settings, contract fingerprint, source hash and request budget. The same model, source contracts and briefs are paired across the two strategies. Each returned draft becomes a normal, unapproved Studio experiment, retaining the raw response and inference metadata.

Jobs allow at most eight generation requests. The provider has a 90-second timeout per request. A soft 180-second job budget is checked between requests; it cannot interrupt an inference already in flight. Progress is stored after each result. The browser polls saved progress and can download the complete record.

A lock prevents simultaneous comparison jobs within one application instance. Provider contention is recorded as a failed request rather than quietly switching models or inserting a fixture. Background jobs use daemon threads, not a durable distributed worker system. A later process can label an orphaned job interrupted when its saved owner process is gone. This is a local single-process learning application; production scheduling, multi-worker locking and restart recovery remain future work.

## 9. Actual local Ollama results

The measured model was **qwen2.5-coder:3b**, using the existing local Ollama service at 127.0.0.1:11434. No model was downloaded and no cloud provider was substituted. Settings were temperature 0, seed 7, num_predict 2600 and num_ctx 12288. A fixed seed helps controlled comparisons but does not establish reproducibility across different hardware or model builds.

The development run ID is `3072a607048f4de68c03fa5c59edb46b`. The reserved run ID is `ed9dafe3ebd54d678769a65ce8946421`. Both completed all eight planned requests. Both strategies were frozen before the reserved run; development results did not lead to prompt changes.

| Split and strategy | Schema valid | Input match | Strict task pass | Required present | Required correct | Comparable correct |
| --- | --- | --- | --- | --- | --- | --- |
| Development · balanced-v1 | 4/4 | 4/4 | 2/4 | 18/20 | 17/20 | 20/21 |
| Development · oracle-check-v2 | 4/4 | 4/4 | 1/4 | 17/20 | 16/20 | 19/20 |
| Reserved · balanced-v1 | 4/4 | 4/4 | 0/4 | 23/31 | 23/31 | 26/26 |
| Reserved · oracle-check-v2 | 4/4 | 4/4 | 0/4 | 23/31 | 23/31 | 26/26 |

The longer checklist prompt did not outperform the baseline on this small sample. It omitted the D01 payout that the baseline included. Both strategies proposed 6,600 cents for D02, whose authored expectation is zero. Both omitted D03 readback history and payment checks. Both passed the cross-member read scenario.

On the reserved tasks, both strategies omitted payout assertions for H01 and H02. Both omitted ledger and history observations for H03 and H04. This explains why all comparable declared assertions could be correct while no complete reserved task passed the rubric.

These are 16 proposals on eight briefs using one model, one seed and one generation per pairing. There are no confidence intervals, repeated-seed estimates, model-ranking claims or productivity claims. qwen2.5:3b is selectable but was not benchmarked in this comparison. The poor completeness scores are retained as an engineering finding, not edited into better raw results.

## 10. Why assertion strength matters

The sensitivity experiment reuses two genuine engineering-reviewed snapshots from the preserved V3 live demonstration. Their approval hashes, current contract fingerprint and schema validity are checked before replay. The first snapshot contains narrow status/revision checks. The second contains strengthened money, event and ledger expectations. Both baseline runs passed.

| Reviewed snapshot | Wrong ledger amount detected | Missing history detected | Total |
| --- | --- | --- | --- |
| Original narrow assertions | No | No | 0/2 |
| Strengthened assertions | Yes | Yes | 2/2 |

This is the concrete reason to check more than a status code: the same apparently successful workflow can contain an incorrect payment or incomplete audit history. Adding the right observations makes the tests sensitive to those defects.

These are two already-known engineering faults, not two new independent defects. They are not added again to the retained 7+5 fault totals. The reviews were engineering demonstrations, not approvals attributed to you.

`artifacts/v4/correction-audit.json` also records two V3 case-edit events covering 20 changed JSON paths. It identifies the original source and checksum and lists before/after changes. This is an audit of actual engineering edits, not a human effort estimate, saved time calculation or learner review count. The 16 V4 comparison drafts were left unedited.

## 11. Rule retrieval and its limits

Retrieval searches the 13 existing synthetic contracts. It tokenizes the query and source text, counts shared terms, gives an exact rule-ID match an additional boost, sorts deterministically and returns at most three matches with their full rule text. An unmatched query returns no evidence.

This small transparent lexical baseline was chosen because every ranking is inspectable and no external service, embedding model or vector database is necessary. A rank is not a relevance probability. Shared generic words or rule-ID fragments can retrieve weak secondary sources. The live investigation demonstrated this limitation by including HC-001 and HC-002 alongside the relevant HC-007 source.

The implementation is a retrieval-assisted explanation baseline, not an enterprise knowledge system. Better token handling, evaluated relevance thresholds and a larger independently reviewed contract collection are sensible future improvements.

## 12. Failure investigation: what actually happened

Investigation accepts an existing experiment ID and stored run ID, not a client-authored list of supposedly observed facts. Code extracts failed assertions, assigns evidence IDs and preserves the original case, step, action, inputs, expected value and observed value. Passing runs abstain without inference. Stale-contract runs and runs without matching source evidence also abstain.

The local model receives those facts and the retrieved contracts. Its response must match a bounded schema with summary, hypotheses and insufficient_evidence. Each hypothesis must cite known evidence and rule IDs, state low or medium confidence, and suggest a next check. Unknown citation IDs or invalid output are saved as invalid_or_unavailable, with the raw response retained where available. No repair is executed.

For the real demonstration, I authored a clearly labeled test fixture with a deliberately wrong expected payout of 91,000 cents for a 100,000-cent claim. The synthetic deductible makes the application payout 90,000 cents. An explicit engineering fixture review allowed that test to execute, producing a real failed assertion. Ollama then received that saved failure.

The model returned structurally valid hypotheses pointing to an incorrect oracle. However, its summary first blamed an application calculation and then said the application followed the rule correctly. It also cited weak secondary sources in one hypothesis. The correct engineering interpretation is that the supplied expected value is wrong; the model's contradictory wording does not change the recorded 91,000-versus-90,000 fact.

The application displays **Observed runner facts** separately from **AI hypotheses · not established causes**. This is deliberate: valid citation IDs establish which documents were referenced, not that the reasoning is supported. The raw explanation is preserved in `artifacts/v4/live-investigation.json`, including the contradiction. No test was automatically edited or approved afterward.

## 13. Tests we now have

The framework retains regression, smoke, sanity, API and browser E2E classifications. Markers select subsets of real tests; a marker name is not a separate test implementation or a certification level. The full regression runs all collected deterministic tests.

New unit checks cover all eight references, incorrect or missing expectations, unmatched input scenarios, consistent claim-ID normalization, optional defaults, generation failures, prompt freezing, first-use/reuse labels, contention, interrupted-job handling, stale contracts, passing-run abstention, citation validation and preservation of facts. The sensitivity demonstration also has a regression check.

New API checks exercise dataset and retrieval endpoints, invalid requests, unknown records, content-type handling, asynchronous job creation and saved progress. Browser checks exercise comparison progress, complete JSON downloads, rule lookup and empty evidence, investigation display, escaping malicious-looking model text and a mobile viewport without page overflow.

Core tests use explicitly labeled provider doubles. They do not call Ollama. This keeps CI deterministic and separates application-control regressions from model quality. The 17 live calls are reported separately and their saved failures remain visible. Generated-case execution still exercises Python service behavior through HTTP-equivalent observations; it is not generated Playwright automation. The manually authored browser suite tests the actual HTTP/UI path.

## 14. Verification, CI and delivery evidence

The final command was `python -m tools.verify`. It ran 297 tests and recorded 297 passes, zero failures and zero skips, including 27 Chromium checks. It also reran both retained fault experiments. Verification output, JUnit XML, environment metadata, contract hashes and a source fingerprint are saved under artifacts. The application reports stale verification if tracked implementation files change afterward.

An earlier full run failed because one browser assertion still required the V3 report title. That migration expectation was corrected, then the complete suite passed. The failure was not ignored or marked skipped.

The GitHub Actions workflow is updated to V4 and remains ready to install Python dependencies and Chromium, run the verifier, and upload evidence. **No remote GitHub Actions execution occurred in this delivery.** No repository was published and no production deployment was made. The current local server is a Flask development server bound to loopback.

V4 evidence is copied into `artifacts/v4`, and a source ZIP plus checksummed manifest is created in releases. The source package excludes the virtual environment, browser binaries, local databases and caches. Saved synthetic experiment JSON provides portable evidence without copying mutable interactive databases. It is a source/evidence package, not an OS installer or cloud release.

## 15. How to learn this in VS Code

Open the standalone folder and inspect `docs/V4_PLAN.md`, then `healthcare_quality/evaluation.py` and `quality_lab.py`. Follow a task from its brief to its reference assertions. Read `score` and identify why removing payout_cents prevents a strict pass even when the remaining declared values are correct.

Use **Run and Debug → V4: start Healthcare Quality Lab** to start port 8894, or run the Flask command in README. The VS Code task labels now identify V4. If the folder is still in Restricted Mode, the project remains inspectable; its trust setting was not changed automatically. The observed VS Code window showed Copilot unavailable in that mode, so this delivery does not claim Copilot executed any work.

For a short exercise, inspect D02 in the saved development record, calculate max(7600 − 10000, 0), and explain why the raw model payout of 6600 is incorrect. For a workflow exercise, compare the original and strengthened snapshots in assertion-sensitivity.json and identify which observation catches a missing history event. `docs/LESSON_04.md` provides the steps.

## 16. AI tools: what ran and how to expand your learning

Codex implemented and explained the framework. Local Ollama actually generated the 16 comparison cases and the failure explanation. VS Code displayed the plan and implementation. pytest and Playwright verified the controls and user flows. These activities are concrete and separately evidenced.

ChatGPT, Copilot and Claude Code were not silently connected to the application or presented as completed integrations. You can use the existing AI tools playbook to ask a second assistant to critique a synthetic task, suggest an assertion, or review a code change, then compare its proposal against the same reference contracts. Do not treat a second assistant agreeing as independent proof. Any generated executable case must still use the review gate.

For a useful multi-tool exercise, ask one assistant why a draft is missing a monetary assertion, ask another to propose a corrected JSON case, and manually check the result against the reference before reviewing it. Keep the original, correction and reviewer note. The value is learning how to evaluate their output; installing more tools is not itself a measure of framework quality.

## 17. Boundaries and remaining V5 work

All healthcare values remain invented teaching contracts. Medicare A, B, C/Advantage and D, commercial, hospital, outpatient, medical, dental and vision examples provide domain vocabulary, not real eligibility or benefit determinations. This system does not move money, process patient data or certify Medicare compliance.

The application is local and uses demo identities and reviewer labels, not authenticated users. It has no production access control, distributed job queue, real payer integration or multi-browser release certification. The reference set is small and authored; reserved references are visible and no longer fresh after their first measured use. Model output can be incomplete, numerically wrong, weakly sourced or contradictory.

V5 can turn this into the final professional showcase: choose a release/deployment target, tighten operational controls for that target, package a guided demonstration, review source and dataset provenance, verify the intended CI environment, and deliver a final architecture and learning report. Improving the prompts or retrieval after these results should be a new versioned experiment; the measured V4 evidence should remain unchanged.

## 18. How to reproduce and inspect the evidence

Run the core suite without a model service:

```sh
source .venv/bin/activate
python -m tools.verify
```

Start the local app:

```sh
python -m flask --app healthcare_quality.app:create_app run --host 127.0.0.1 --port 8894
```

Live requests are opt-in. They create new records and use the installed local model. Reusing the reserved split will not restore its original freshness:

```sh
python -m tools.v4_live --split development
python -m tools.v4_live --split held_out
python -m tools.v4_live --split investigation
python -m tools.v4_live --split sensitivity
```

Inspect development-comparison.json and held_out-comparison.json for frozen jobs and aggregate counts; proposal-*.json for raw model drafts; authored-failure-experiment.json and live-investigation.json for observed facts and explanation; assertion-sensitivity.json for the two reviewed snapshots; correction-audit.json for the exact engineering changes; and verification.json for the deterministic suite.

The live runner's fixed artifact names represent the latest explicit rerun, while SQLite retains separate job IDs. Copy an earlier portable evidence directory before deliberately overwriting its latest-run files. The delivered checksummed release preserves this delivery's evidence.

## 19. Technical references

Ollama's generate endpoint accepts a model, prompt and structured format. This project supplies a JSON schema and disables response streaming. [Ollama generate API](https://docs.ollama.com/api/generate).

Ollama documents passing a schema in the format field and including it in the prompt. The project follows that pattern and independently validates the returned data; schema conformity does not establish business correctness. [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

Playwright provides the pytest integration used for browser tests and supports headed execution, browser selection and tracing options. [Playwright pytest reference](https://playwright.dev/python/docs/test-runners). pytest markers support selecting named groups; the project registers smoke, sanity, regression, unit, API, E2E and AI markers explicitly. [pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html).
