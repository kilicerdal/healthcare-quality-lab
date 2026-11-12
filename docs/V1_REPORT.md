# Healthcare Quality Lab V1 Engineering Report

**Version:** 1.0.0 — Reliable foundation

**Implementation date:** November 11, 2026, America/New_York

**Project location:** `/Users/erdalkilic/Documents/Healthcare Quality Lab`

**Delivery outcome:** V1 is a working local application with explicit synthetic healthcare contracts, a Python evaluator, automated tests at three layers, traceable evaluation results, and recorded defect-detection evidence. It includes an actual local AI review exercise and an engineering assessment of the model's mistakes. AI-generated executable tests remain planned for V3.

## 1 Why we are building this framework

The long-term goal is to build an AI-assisted healthcare quality engineering framework that you can demonstrate and explain. You should be able to describe a requirement, understand its risks, judge a proposed test, run it, investigate an unexpected result, and explain the evidence to another person.

An AI tool can produce plausible test ideas before a project has reliable requirements. That speed is useful, but it creates a problem: who decides whether an AI-generated expected result is correct? If the model invents a coverage assumption or an engineer simply copies the application's answer into a test, both the application and its tests may agree on the same mistake.

V1 addresses that problem first. It creates a small system whose contracts are written down and whose expected outcomes are independently specified. We can inspect the behavior, deliberately break parts of it, and verify that our tests notice. Later versions can evaluate AI proposals against this foundation instead of treating model output as truth.

The practical learning goal is equally important. You now have runnable examples of Python functions, validation, JSON data, HTTP endpoints, pytest fixtures and parameterization, Playwright browser actions, and recorded evidence. The project connects these concepts through one healthcare scenario rather than presenting unrelated tutorials.

## 2 Where V1 was built and how it stays separate

All V1 project changes were made inside `/Users/erdalkilic/Documents/Healthcare Quality Lab`. This is a direct child of Documents and is not nested inside Generative AI framework or Insurance claim framework. This V1 implementation did not copy, move, inspect, or modify files in those earlier project folders.

The project has its own `.venv` Python environment, `.browsers` Chromium installation, `.vscode` settings, application package, test folders, documentation, and evidence directory. Temporary authoring helper scripts were staged in `/private/tmp`; the application does not depend on them. The installed Ollama service was accessed over loopback for the optional review; no model was downloaded or reconfigured.

The reason for this separation is ownership and repeatability. A dependency change or test run here should not change another project's environment. The README and VS Code tasks all refer to this standalone folder. A virtual environment should be recreated from the dependency file when moving machines, rather than copying it to a different path.

## 3 What V1 includes and what it deliberately leaves for later

V1 includes eight synthetic plan configurations, seventeen service categories, seven written rules, a stateless evaluator, a local browser workspace, JSON evidence export, unit tests, API tests, Chromium end-to-end tests, smoke/sanity/regression selectors, seven authored defect seeds, a verification recorder, and a GitHub Actions definition. The browser also contains a coverage explorer, rulebook and five-version roadmap.

The application does not yet store members, patients, policies or claims. It does not submit claims to a payer, calculate actual benefits, perform enrollment, apply real annual accumulators, generate executable AI tests, approve AI output, or deploy to a server. Those features would require additional requirements and validation. Keeping V1 stateless makes a first test run easy to understand and prevents test results from depending on records left by another scenario.

The optional Ollama exercise reviews supplied contracts and suggests test ideas as text. It is intentionally separate from claim evaluation. A claim decision always comes from deterministic Python, not from an LLM.

## 4 The healthcare domain and its limits

The configuration names cover Medicare Part A, Part B, Medicare Advantage / Part C, Part D, commercial PPO, commercial HMO, standalone dental and standalone vision. Advantage is represented as Part C, not a fifth Medicare part. Medicare.gov identifies A with hospital insurance, B with medical insurance, D with drug coverage, and Advantage/Part C as an alternative that bundles benefits. The official naming source is [Parts of Medicare](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/parts-of-medicare).

V1's service categories include hospital, medical, outpatient, prescription, dental, vision, hearing, durable medical equipment, preventive care, mental health, maternity, rehabilitation, emergency, laboratory, skilled nursing, hospice and home health. These categories provide room for different testing risks. The exact allowed combinations are authored software fixtures in `healthcare_quality/data/plans.json`.

For commercial context, HealthCare.gov describes Marketplace benefit categories and notes that actual services vary. Adult dental and vision should not be assumed universal. That reference is [Marketplace health benefits and coverage](https://www.healthcare.gov/coverage/what-marketplace-plans-cover/). It does not establish benefits for every employer or commercial policy.

Every V1 plan deliberately uses the same invented $100 deductible and $2,000 payout cap per evaluation. This simplifies the learning examples. Those figures are not Medicare rates, actual commercial plan costs, or annual limits. The network and authorization arrays are also invented. A service omitted from a fixture does not establish that real Medicare never covers that service; real exceptions and plan-specific conditions are outside the model.

## 5 The seven contracts and the risks they address

The rulebook is the project's test oracle: the reference for deciding what correct behavior means. IDs make it possible to link a request, assertion, denial and defect experiment to the same contract.

| Rule | Purpose | Why it matters |
| --- | --- | --- |
| HC-001 | Validate request shape, identifiers, amount and boolean flags | Prevent malformed or ambiguous data from producing credible-looking financial results |
| HC-002 | Reject inactive coverage | Detect payment when the teaching policy is inactive |
| HC-003 | Enforce the selected synthetic service matrix | Detect approval of a service absent from that contract |
| HC-004 | Apply the fixture's network control | Detect a bypassed network restriction |
| HC-005 | Require authorization for configured services | Detect a missing authorization check |
| HC-006 | Apply the prescription formulary flag | Detect acceptance of an excluded synthetic prescription |
| HC-007 | Subtract deductible, floor at zero, then cap payout | Detect overpayment, negative payout or a missing cap |

The validation order is intentional: input, active coverage, benefit, network, authorization, formulary, payout. Evaluation stops at the first business denial. For example, a Part D hospital request outside the network receives SERVICE_NOT_COVERED because that fixture lacks the service; it does not first receive OUT_OF_NETWORK. Tests explicitly check precedence so a future refactor cannot silently change the contract.

A passed trace entry means that particular request was not denied by that check. It does not mean all cases for that rule have been covered. Some controls are irrelevant to a request—for example, a formulary flag on a non-prescription service—and a passing entry does not imply the control was actively exercised.

## 6 The architecture and why the pieces are separated

The flow is: written contracts → Python evaluator → Flask API → browser result → exported evidence. The automated suite exercises that flow at different boundaries.

`catalog.py` loads the JSON contracts and calculates a SHA-256 fingerprint. A fingerprint is a compact identifier for exact input data; changing the contracts changes that identifier. It supports comparison and provenance, not cryptographic signing or proof that the contracts are correct.

`claims.py` validates a request and makes a decision. It does not import browser code, call AI, or store claims. This makes direct unit tests fast and readable. `app.py` exposes that logic through Flask and serves the browser interface. It handles HTTP-specific behavior such as JSON content types, invalid requests and payload limits without mixing those concerns into the payout formula.

The browser interface sends requests and displays the returned facts. It does not contain a second implementation of the insurance rules. A Playwright test therefore checks a real browser-to-server flow rather than comparing two duplicated JavaScript calculations.

`tools/` contains verification, fingerprinting, the defect benchmark and optional AI review. `tests/` contains assertions and a separate set of explicitly authored expected outcomes. `docs/` explains the project, and `artifacts/` holds generated evidence. These boundaries provide room to grow without creating unnecessary services or infrastructure in V1.

## 7 The tools and the reason for each choice

| Tool | What it does in V1 | Reason for using it |
| --- | --- | --- |
| Python | Business rules, HTTP integration and tooling | One readable language for application logic and automated tests |
| Flask | Local UI routes and JSON endpoints | A small HTTP layer that is easy to inspect and test |
| pytest | Test discovery, assertions, fixtures, parameterization and suite markers | Supports readable tests and reusable isolated setup |
| Playwright for Python | Real Chromium browser automation | Checks visible user behavior through the same Python testing workflow |
| HTML, CSS and JavaScript | Interactive browser workspace | Provides a demonstrable interface without a separate frontend build toolchain |
| VS Code | Editing, debugging and task entry points | Lets you navigate code, run a single test and watch browser automation |
| Ollama | Optional review using a locally installed model | Creates a real AI learning exercise without a cloud inference account |
| GitHub Actions | Prepared automation definition | Makes the same verification command available for a future remote repository |

The verified environment used Python 3.13.18, pytest 8.4.2, Playwright 1.56.0 and Flask 3.1.2. Direct dependencies are pinned in `requirements-dev.txt`; a full installed-package snapshot is saved in `artifacts/environment.txt`. The installed snapshot records this environment, while a fresh installation may resolve different transitive dependency versions. We have not claimed a fully locked cross-platform release.

Playwright's official [Python installation guide](https://playwright.dev/python/docs/intro) describes the pytest plugin approach used here. Flask's [quickstart](https://flask.palletsprojects.com/en/stable/quickstart/) explains its local development server. The V1 server is intended for loopback development, not production hosting.

## 8 What you can see and do in the application

The claims workspace lets you select a contract and service, enter an amount in cents, and toggle active coverage, network, authorization and formulary flags. It returns an approved or denied teaching decision, a reason code, a payout and the ordered rule trace. Three guided examples load a covered commercial claim, a missing Advantage authorization and a Part D dental benefit mismatch.

The coverage explorer displays all eight contracts and filters them into Medicare, commercial and supplemental families. Each card shows its service list, network behavior and authorization requirements. The rulebook explains the contracts and risks. The roadmap makes the distinction between delivered V1 behavior and planned V2–V5 work visible.

The evidence export downloads the full result as JSON. This includes the normalized request, version, contract fingerprint, decision, payout and trace. It provides a concrete object you can inspect or attach to a demonstration. It is an evaluation record, not an immutable audit trail or persistent claims database.

The dashboard's test statistic comes from a recorded verification file. It does not use a hard-coded success count. The application compares the recorded source fingerprint with current implementation files and marks the result stale if they differ. This avoids displaying an old passing run as evidence for newly changed code.

## 9 How the automated testing layers differ

Unit tests call Python directly. They check calculations, boolean-versus-integer validation, malformed identifiers, limits, contract precedence, isolation, catalog snapshots and the AI adapter's response contract. Expected outcomes are explicit; the tests do not call the production payout formula to calculate their own expected number.

API tests use Flask's in-process test client. They verify JSON responses, HTTP status codes, health and catalog routes, denial evidence, malformed JSON, wrong content types, oversized requests, wrong methods and report availability. They are HTTP contract checks inside the process; they do not measure network transport or a deployed reverse proxy.

Browser E2E tests launch real Chromium against a temporary loopback HTTP server. They exercise the JavaScript form, Flask route, Python decision and visible result. Browser contexts are isolated, and the fixture shuts down the server after the suite. No external payer or model is required for these checks.

Smoke, sanity and regression are selection purposes rather than additional technical layers. Three smoke tests check the essential function, application availability and a browser evaluation. Three sanity tests focus on authorization across Python, API and browser boundaries. The regression marker selects all 101 implemented checks. The same test can be both an E2E test and part of a smoke or regression suite.

## 10 The recorded verification results

The final local verification completed on 2026-11-11T21:06:59.253907-05:00 using `python -m tools.verify`.

| Evidence | Recorded result |
| --- | --- |
| Total automated test cases | 101 passed, 0 failed, 0 skipped |
| Unit cases, including mocked AI adapter checks | 77 passed |
| API contract cases | 16 passed |
| Real Chromium browser cases | 8 passed |
| Explicit golden business examples | 28 reference examples, zero mismatches |
| Authored seeded defects detected | 7 out of 7 |
| Verification command duration | 4.35 seconds in this environment |
| Browser coverage | Chromium only; desktop and a 390 × 844 mobile-sized viewport |
| Remote GitHub Actions execution | Not performed |

The browser checks cover a normal claim, missing authorization and correction, unsupported benefit denial, zero payout at the deductible, coverage filters/rulebook/roadmap navigation, JSON download contents, mobile layout/evaluation, and opening the engineering report. The mobile test also checks horizontal overflow; screenshots were inspected for layout. This is not a complete accessibility audit or a test on a physical phone.

The evidence files are `artifacts/verification.json`, `pytest-results.xml`, `pytest-output.txt`, `defect-benchmark.json`, and desktop/mobile screenshots. The verification source SHA-256 is `59b2814c5beedb08e988f204492e4685845b8b06c6a1b36246a19ce09ec815ac`. No code-coverage percentage, exhaustive input coverage or production reliability percentage was measured. A case count is evidence of executed checks, not a completeness score.

## 11 Why the deliberately broken variants matter

A test suite that passes on a correct implementation might still be too weak to detect a defect. The V1 benchmark addresses a small part of that risk by running known faulty variants against explicit expectations.

| Seeded defect | What the faulty variant does | Independent expectation that detects it |
| --- | --- | --- |
| Eligibility bypass | Approves an inactive request | G09 expects INACTIVE_POLICY |
| Coverage bypass | Approves the fixture's unsupported dental service | G10 expects SERVICE_NOT_COVERED |
| Network bypass | Approves an out-of-network HMO request | G11 expects OUT_OF_NETWORK |
| Authorization bypass | Approves the configured hospital request without authorization | G12 expects AUTH_REQUIRED |
| Formulary bypass | Approves a non-formulary prescription | G13 expects NON_FORMULARY |
| Deductible omission | Pays 100000 cents rather than 90000 | G14 expects 90000 cents |
| Limit omission | Pays 290000 cents rather than the 200000 cap | G18 expects 200000 cents |

All seven were detected, while the reference implementation passed all 28 golden examples. Fault injection is exposed only as an explicit Python keyword for experiments. HTTP requests cannot turn it on; an extra defect field fails request validation.

These are seven authored seeds chosen with knowledge of the suite. They are not an exhaustive mutation analysis, a blind benchmark, proof against every future bug, or a measure of real insurance accuracy. Their value is concrete: you can point to a business risk, show the faulty observed result, and identify the assertion that catches it.

## 12 The actual local AI exercise and what it taught us

The optional review actually ran with the already installed `qwen2.5:3b` model through Ollama on `127.0.0.1:11434`. It received only synthetic contracts, not neighboring project files or patient information. Its recorded request used temperature 0, an 8192-token context setting and a maximum of 1000 generated tokens. The run reported 1703 input tokens, 350 output tokens and approximately 7.55 seconds of request latency. These figures describe one run, not a performance benchmark.

The model returned three structurally valid suggestions citing HC-007. Some were wrong. It said that above-limit or at-limit claims should be denied, even though HC-007 explicitly says to subtract the deductible and cap an approved payout. It also described deductible cases as unspecified despite their being present in the supplied contract.

One suggestion had a correct zero-payout idea at the deductible, but that idea was already specified and tested. Another mixed a valid below-deductible boundary with an invalid denial expectation. The third incorrectly expected denial at the cap. These outputs show that valid JSON and a real rule citation are insufficient checks for semantic correctness.

The engineering review preserved the raw response in `artifacts/ai-review.json` and recorded findings in `artifacts/ai-review-assessment.json`. No incorrect business-rule change was applied. A targeted regression test now verifies that a 200000-cent claim is approved with a 190000-cent payout after the 10000-cent deductible. That assertion follows the written contract independently of the model's suggestion.

This assessment was performed by Codex against the contracts and tests; it is not recorded as a completed human approval by you. The model had not inspected the test suite and could not truthfully establish that a test was missing. The review script cannot execute code, approve tests or change files in the application. It has explicit timeout, output-size, completion, schema and source-ID checks. Model unavailability or malformed output produces a failure record instead of a silent canned response.

## 13 How we will learn multiple AI tools

Codex was used for implementation, explanation, test execution and engineering review in this delivery. Ollama was used for the live local review described above. ChatGPT, GitHub Copilot and Claude Code have prepared exercises in `docs/AI_TOOLS_PLAYBOOK.md`; separate sessions or integrations for those tools were not executed as part of V1.

The exercise format is consistent: give each tool the same synthetic requirement, inspect its proposed expected values, identify unsupported assumptions and duplicates, record corrections, and run a reviewed assertion where appropriate. You learn how to provide context, ask for evidence, detect invented rules and compare actual outcomes. Tool variety supports learning, but it does not replace a common evaluation method.

No new paid account, external model API or subscription was configured. Optional tools depend on your own account access and setup. V3 will integrate structured AI-generated proposals and approval into the application. V1's review exercise provides early experience without claiming that later workflow is already complete.

## 14 CI, VS Code and daily use

VS Code has a project-local interpreter setting, pytest discovery, a launch configuration for the local app, a debugger entry for the first deductible test, and tasks for full verification, smoke, sanity, visible browser checks, the benchmark and local AI review. The claims engine and test file were opened in the Healthcare Quality Lab window for inspection.

The editor was observed in Restricted Mode. Folder trust remains your choice after inspecting the code; the verified terminal runs do not require us to change that security setting. In a trusted local development window, the launch and testing features can be used directly.

`.github/workflows/ci.yml` installs Python dependencies and project-local Chromium on an Ubuntu runner, runs the same verification command, and uploads results even if a check fails. It does not call Ollama or require model secrets. Core CI stays deterministic, while live-model experiments remain separately recorded.

The workflow is prepared locally. No remote repository was created or pushed, no GitHub run was observed, and no deployment or CD pipeline has been executed. Remote execution and a selected deployment target belong to later release work. A passing local run should not be described as a passing GitHub Actions run.

## 15 What V1 achieved and how to judge it

V1 achieved a runnable foundation that connects requirements, behavior, assertions and evidence. You can inspect the synthetic coverage contract, submit an evaluation, explain a denial, export its trace, run the tests and show specific defects being caught. You also have an example of an actual local AI suggestion being challenged rather than blindly adopted.

The acceptance conditions for this version were observable: the app works locally, every recorded automated check passes without skips, the seven authored defects are detected against a passing reference, the documentation explains the decisions, and the report is available both as editable Markdown and printable HTML. The verification record supports the technical checks; the lesson and demonstration guide support your learning.

Your personal understanding has not been assessed by a test run. Read `docs/LESSON_01.md` and explain why a claim amount equal to the payout cap is not automatically denied. Then follow `docs/DEMO.md` and describe what each evidence field proves. That is how the delivered system becomes your demonstrable knowledge rather than code you merely possess.

## 16 Remaining limitations and technical risks

The healthcare model is intentionally incomplete. It has no actual coverage criteria, coding standards such as CPT/HCPCS/ICD, enrollment dates, coordination of benefits, appeals, emergency exceptions, coinsurance, negotiated allowed amounts or annual accumulators. It has no persistent claim lifecycle, member identity, roles or concurrency model. These require their own contracts rather than assumptions added by a model.

The local Flask development server is not production infrastructure. V1 has no authentication, persistent audit store or deployment hardening. Requests and exported evidence contain synthetic data; real patient or member information should not be introduced as a shortcut to realism. JSON files and hashes support learning provenance, not tamper-proof audit claims.

Browser verification covers Chromium only. A mobile-sized viewport is not a physical-device test. No load test, full accessibility audit, penetration test, formal regulatory validation or comprehensive code-coverage analysis was performed. Local model quality was observed in one small review request; no claim is made about all Ollama models or the relative quality of different AI products.

The final report is a snapshot of this version. The dashboard detects changes in implementation files through a source hash, but a hash does not authenticate authorship or prevent edits to local artifacts. The version's raw evidence should be retained when future versions are compared.

## 17 The path from V1 to V5

| Version | Purpose | Next acceptance evidence |
| --- | --- | --- |
| V1 | Establish reliable requirements, behavior and tests | Delivered local verification, seven-seed benchmark, optional AI review and this report |
| V2 | Add isolated healthcare workflows and reusable components | Lifecycle, duplicates, permissions, cleanup and broader regression evidence |
| V3 | Generate reviewable test proposals with local AI | Schema/source validation, explicit human approval and controlled execution evidence |
| V4 | Evaluate AI usefulness and investigate failures | Reviewed and held-out examples, prompt experiments, corrections and grounded explanations |
| V5 | Package and demonstrate a release workflow | Actual remote CI results, versioned release, chosen deployment/rollback evidence and final showcase |

`docs/ROADMAP.md` gives the planned acceptance criteria for each version. V2–V5 remain plans. This delivery stops at V1 so you can inspect it before we add more complexity. Every later version should receive its own report with the same separation between purpose, implementation, evidence and limitations.

## 18 How to start, inspect and reproduce V1

Open only `/Users/erdalkilic/Documents/Healthcare Quality Lab` in VS Code. Select the project interpreter `.venv/bin/python`. In a terminal in that folder:

```sh
source .venv/bin/activate
python -m tools.verify
python -m flask --app healthcare_quality.app:create_app run --host 127.0.0.1 --port 8891
```

Open `http://127.0.0.1:8891`. The Engineering report link serves this report. Stop the local server with Ctrl+C. Tests create their own temporary server, so the interactive server does not need to be running for verification.

For focused work, use `python -m pytest -m smoke -v` or `python -m pytest -m sanity -v`. To watch browser actions, run `python -m pytest -m e2e --headed --slowmo 350 -v`. To repeat the local model exercise when Ollama is running, use `python -m tools.ai_review --model qwen2.5:3b`; preserve the original artifact before rerunning if you want to compare outputs.

For a new machine, follow the README's fresh-environment setup, including project-local browser installation. The report's recorded results describe the tested machine; your run produces new evidence rather than inheriting this machine's success automatically.

## 19 File guide and plain language glossary

| Location | What to look for |
| --- | --- |
| healthcare_quality/data/rules.json | Exact written rules and risks |
| healthcare_quality/data/plans.json | Invented plan matrix and amounts |
| healthcare_quality/claims.py | Validation order and decision logic |
| healthcare_quality/app.py | UI routes, JSON API and HTTP errors |
| tests/data/golden.json | Independent expected outcomes for 28 examples |
| tests/unit/test_claims.py | The first deductible test and the AI-related correction assertion |
| tests/api/test_api.py | Request/response contract checks |
| tests/e2e/test_browser.py | Full browser workflows |
| tools/verify.py | Evidence recording and pass/fail criteria |
| tools/benchmark.py | Known faulty variants and detection evidence |
| tools/ai_review.py | Optional local-model request and output checks |
| artifacts/ | Actual execution evidence and AI-review findings |
| docs/ | Report, roadmap, lesson, demo and AI learning exercises |

A **requirement** states expected behavior. A **test oracle** is the reference used to decide whether an outcome is correct. An **assertion** compares observed behavior with an explicit expectation. A **fixture** provides repeatable setup and cleanup. An **API** is the application's structured request/response boundary. An **E2E test** checks a complete user flow through connected layers. A **regression suite** rechecks implemented behavior after changes. A **seeded defect** is a deliberately faulty variant used to challenge tests. A **fingerprint** identifies exact recorded inputs or source content. An **AI proposal** is a suggestion that still requires verification.

The central result of V1 is that these terms now refer to working, inspectable examples in your own standalone project.
