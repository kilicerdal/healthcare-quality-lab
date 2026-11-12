# Healthcare Quality Lab V5 Engineering Report

## 1. What V5 delivers

V5 turns the existing healthcare quality lab into a reproducible local showcase with its own private GitHub repository. It adds a guided presentation page, project-local setup, Waitress serving, runtime storage readiness, request tracing, checked release packages, verified staging, activation and rollback, plus a CI workflow that tests and boots the packaged application.

The main purpose is to complete the engineering story. V1 explained what correct behavior means. V2 exercised a stateful claim lifecycle. V3 let local AI propose tests under explicit review. V4 measured how useful those proposals actually were. V5 demonstrates how to reproduce, inspect, test, package and launch that work with evidence attached to each claim.

The deterministic local suite passes **325 tests: 244 unit, 52 API and 29 Chromium browser tests**, with zero failures and zero skips. The retained authored fault experiments detect seven evaluator faults and five workflow faults against passing reference examples. These are finite checks, not exhaustive correctness or compliance certification.

Local release rehearsal status: **passed** — actual V4 and V5 archive startup, two full claim journeys, rollback with earlier state preserved, and V5 reactivation with its own state preserved. Candidate release ID: `v5.0.0-77c5120c7965`..

GitHub CI status: **PENDING_CI**. The new private repository is [kilicerdal/healthcare-quality-lab](https://github.com/kilicerdal/healthcare-quality-lab). This report records remote execution only after an actual Actions result is available; a workflow file alone is not evidence that CI ran.

## 2. Where the work belongs

The standalone project remains `/Users/erdalkilic/Documents/Healthcare Quality Lab`, directly under Documents. No Generative AI, Insurance claim framework, website project or existing GitHub repository was used as a destination or dependency. You explicitly authorized a new private repository named healthcare-quality-lab, and it was created separately under your kilicerdal account.

The existing V1–V4 source archives, sidecar manifests, reports and versioned evidence remain preserved locally. The V4 archive checksum was verified at the start. The current checkout is V5; earlier archives preserve the earlier implementations. Historical reports remain available at /reports/v1 through /reports/v4, while /report and /reports/v5 serve this report.

Mutable claim databases, Studio records and evaluation jobs stay under project-local .local directories. Source releases exclude those databases, the virtual environment, browser binaries, caches and environment files. Portable synthetic JSON evidence is included, so someone can inspect the measured results without copying the interactive state.

GitHub publication is private source collaboration, not public website deployment. The runtime target for this delivery is explicitly local loopback. There is no hosted patient-facing service, real payer integration, external payment or public cloud endpoint.

## 3. Why these features were worth building

A useful showcase needs more than a screen full of green checks. Another engineer should be able to understand the requirements, install the dependencies, run the relevant tests, inspect a raw AI proposal, identify the expected-result oracle, and start the exact packaged code being demonstrated.

Earlier versions established test design and AI controls. The remaining gap was release confidence: does a package include the right source? Can it be checked before extraction? Does its application start from the staged directory rather than accidentally importing the original checkout? Can we return to a known earlier version without discarding its synthetic state? Do runtime failures produce useful evidence?

V5 addresses those questions with small, inspectable Python tools. It avoids claiming a production deployment when we have only exercised a local target. Its release checks establish byte consistency and tested behavior for this configuration, not general platform security, regulatory compliance or clinical correctness.

## 4. The guided showcase you can use

Open http://127.0.0.1:8895/#showcase. The page introduces the full five-version journey, shows the recorded test result separately from runtime readiness, links each milestone to its working feature, and provides a short demonstration sequence.

The milestone cards lead to the evaluator, claim lifecycle desk, AI Test Studio and AI Quality Lab. The evidence area offers fixed, allowlisted downloads: current verification, V4 development and reserved comparisons, the raw AI explanation, assertion sensitivity and V5 release rehearsal when available. Missing evidence is visibly labeled unavailable rather than manufactured.

The headline count is shown as verified only if the saved source fingerprint matches the current implementation. A stale record displays Unverified. The separate readiness indicator queries the runtime stores. A ready process does not retroactively make an old test record fresh, and a passing test record does not prove the running store is available.

The page preserves the V4 findings: sixteen real local proposals are historical measurements, not new V5 inference. A saved model explanation remains a hypothesis even when its citation IDs are structurally valid. This keeps the demonstration useful for learning rather than presenting only flattering results.

## 5. Technology choices and setup

Python remains the main language. Flask serves the application and JSON APIs. pytest runs unit and API tests and integrates with Playwright Python for real Chromium browser E2E tests. SQLite persists synthetic claims and experiment records. HTML, CSS and JavaScript implement the local interface. Existing local Ollama provides structured case generation and explanations.

V5 adds Waitress 3.0.2 as the WSGI server. It is configured explicitly for 127.0.0.1 with eight threads. This removes the Flask development server from the V5 serving command while keeping the target local. Threads allow other requests to proceed while a bounded local inference occupies one request; they do not make the application a distributed production system.

Runtime requirements are separated into requirements.txt: Flask, jsonschema and Waitress. requirements-dev.txt includes those plus pytest, Playwright and pytest-playwright. Versions remain pinned to the environment used for verification. Python 3.13 is the tested delivery environment; the bootstrap's minimum interpreter check is not a claim that every supported Python/platform combination was tested.

`python3 -m tools.bootstrap --browser` creates a project-local virtual environment if absent, installs the dependency set and optionally Chromium into .browsers. `--dry-run` shows the exact commands. `--runtime-only` omits test dependencies. It does not delete an existing environment, install global packages, download an Ollama model or modify another project.

## 6. Runtime health, readiness and request tracing

/api/health remains a small process/version response. /api/ready opens the three expected SQLite stores and queries their expected tables with a short timeout. It returns 503 if an expected store or table is unavailable. Each probe connection is explicitly closed. It deliberately does not contact Ollama: the core explorer and workflow should remain usable when the optional local model is offline.

Readiness establishes current database access and table availability. It does not prove write availability, future capacity, AI quality, production access control or benefit correctness. These boundaries are stated in the response and operations guide.

Every response receives an application-generated X-Request-ID and Server-Timing duration. Structured request records include the generated ID, method, route pattern, status and elapsed milliseconds. The application enables INFO logging in its actual runtime, so those records are not merely visible under a test logger.

The records omit request bodies, query strings and headers. Using a route pattern such as /api/claims/<claim_id> avoids copying a concrete identifier into the application request record. The tests inject distinctive payload/query strings and verify they do not appear in those structured records. This is a scoped logging design, not a guarantee about every external proxy or server log someone could later add.

Storage errors preserve an explicit 503 response and a trace ID without exposing the injected database exception text. Additional response headers disable framing and referer disclosure. These small controls improve the local demonstration; they do not replace authentication or a threat assessment for public hosting.

## 7. The source release and its evidence

`python -m tools.release build` requires a current-version verification record with status passed and a matching source fingerprint. It refuses an existing archive or manifest filename. This prevents an old successful test run from silently blessing changed implementation code and prevents overwriting a delivered release.

The source fingerprint includes application code, templates, assets, tests, tools, runtime/development requirement files, pytest configuration and the CI workflow. Reports and evidence are separately captured by the per-file archive manifest; changing narrative documentation does not pretend to rerun code tests. The builder also checks that the implementation fingerprint did not change during packaging.

The ZIP contains source and portable synthetic evidence under one named root. Its sidecar records version, creation time, archive SHA-256, source fingerprint, individual file digests and verification counts. The interpreter, installed dependencies, browser binaries and local state are deliberately separate. A release ZIP is therefore a source/evidence bundle, not a self-contained executable installer.

A checksum proves consistency with the supplied manifest. It does not authenticate its author: someone able to replace both files could generate a consistent but different pair. This delivery does not claim signed attestations, a trusted build service identity or a complete software supply-chain security program.

## 8. Validation before and after staging

The inspect command verifies the archive checksum and every listed member digest. It requires an exact match between the manifest member set and ZIP contents. It rejects unsafe paths, absolute or parent traversal names, backslash paths, duplicate members, symlinks, excluded local/environment paths and invalid root/type entries. It limits compressed and expanded sizes to 256 MiB and entry count to 10,000.

Staging validates the pair before creating the destination payload, checks member names/types/digests again while copying, and writes into a temporary directory. Only a verified complete tree is renamed into its release directory. This avoids treating a partially copied payload as an installed release.

The release ID combines semantic version and the archive digest prefix. The same version can have a distinct candidate and final package because the archive bytes and documentary evidence differ; their IDs identify that distinction. Restaging an identical package verifies the existing tree rather than overwriting it.

Activation and serving both recheck the staged file set and digests. Changed or unexpected source files block activation. Runtime bytecode caches are excluded from the tree comparison, while Python source and other package files remain checked. The staged manifest is trusted local metadata tied to the inspected package; the mechanism is integrity checking, not protection against a fully privileged attacker rewriting the entire deployment tree.

## 9. Activation, state isolation and rollback

The active release is selected by current.json under a chosen project-local deployment directory. Activation verifies the requested payload, retains the previous ID and atomically replaces the pointer through a temporary file and os.replace. The release payload and mutable state are separate.

Every release ID uses its own persistent synthetic state directory. Switching back restores that release's earlier state, and returning to the new release retains its independent records. The release tools do not migrate, synchronize, reset or delete databases across versions. This choice makes a teaching rollback understandable without inventing a production schema-migration strategy.

The pointer is read when a server starts. Activation does not hot-swap a running process. Stop the current server, change the pointer, then start the selected release again. The serve command verifies the payload and replaces its launcher process with a fixed trusted Python/Waitress launch, using the staged directory as its working directory and the separate state path as configuration.

The command binds only loopback. Dependencies come from the already prepared environment. There is no automatic system service, public routing, container registry, cloud account, password handling or model installation in this local deployment flow.

## 10. What the real release rehearsal checks

The rehearsal tool can stage the preserved V4 archive as a baseline and a newly built V5 candidate, boot each through Waitress and issue actual HTTP requests. It does not use Flask's in-process test client for these checks, and it does not call Ollama.

For each main journey it checks health/version, a 100000-cent PPO medical evaluation with payout 90000, customer submission, duplicate rejection, cross-member read rejection, finance rejection before approval, adjuster approval, finance payment and final readback. The final claim must be paid at revision 3 with three events and a 90000-cent ledger entry. Invalid generation input must be rejected before inference.

For V5 it also checks readiness and the generated request ID. The rollback phase restarts V4, verifies its earlier claim/ledger still exists and that the V5 claim is absent from V4 state. Reactivation restarts V5 and verifies its earlier ledger remains. All created records are synthetic and confined to the rehearsal's separate state directory.

The first archived-runtime attempt exposed a real integration issue: Waitress normalized X-Request-ID to X-Request-Id, while the rehearsal client used a case-sensitive dictionary lookup. HTTP header names are case-insensitive. The client now normalizes them, a regression test covers the observed spelling, and rehearsal-attempt-1.json preserves the failed attempt. The application had returned the trace ID correctly.

The saved record identifies the candidate archive and hash-derived ID. It records each phase, version, observed values, rollback outcome and zero live model calls. This is direct local release evidence, not an assertion that an arbitrary production host can deploy or roll back safely.

## 11. Tests added in V5

Release unit tests cover member integrity, staging/reuse, activation/rollback, state preservation, changed archives, traversal and excluded paths, missing or incorrect member digests, duplicate ZIP entries, symlinks, changed staged payloads, unexpected files, invalid release IDs, missing rollback targets, stale verification and refusal to overwrite existing release files.

Resilience tests inject a provider timeout and verify the existing 90-second request parameter and explicit ProviderError, with no fallback. Another test fails a generation then succeeds, proving the generation lock was released. A deterministic clock forces the comparison's soft budget to expire between calls, proving the job records failure and releases its lock without making inference requests.

API tests check ready/unavailable storage states, fixed evidence download IDs, request IDs, timing headers, safe structured logging and explicit storage-error responses. Browser tests exercise the guided showcase, milestone links, evidence downloads, workflow navigation and a narrow mobile viewport without page overflow. Bootstrap tests verify the runtime-only and optional browser command plans.

The complete suite retains regression, smoke, sanity, unit, API, AI and E2E classifications. Those markers select implemented behavior; their names are not a separate quality certificate. Core tests use clearly labeled provider doubles. V4's seventeen live local calls remain a separate quality experiment, and V5 adds no new model-quality claims.

## 12. GitHub repository and actual CI

You authorized a brand-new private repository. The connected GitHub profile identified kilicerdal; repository creation was performed through your working GitHub CLI login because the connector did not expose repository creation. The new repository was independently verified private. Existing repositories were left unchanged.

The workflow uses read-only repository contents permission. On push, pull request or manual dispatch it checks out the code, installs Python 3.13 dependencies and Chromium, runs the full verifier and known-fault experiments, builds and inspects a source release, starts its staged Waitress runtime for an actual HTTP journey, then uploads release and test evidence. Concurrent runs on the same ref can supersede older runs.

The CI rehearsal uses the current package only. It does not claim the historical V4 rollback check, because historical ZIPs remain locally preserved rather than tracked as Git source. Local rehearsal separately proves that finite rollback path. Uploaded artifacts are retained for fourteen days under the workflow configuration; a private release asset is a separate delivery mechanism if published.

The final remote result and run URL are recorded below after observation. Provider doubles keep CI independent of a developer's Ollama installation. CI does not install a model, publish a public application or connect to an unspecified hosting account.

## 13. What we learned about AI and test quality

The V4 measurements remain part of the final showcase because they are more informative than a claim that AI generated many tests. All sixteen drafts were structurally valid and matched the requested inputs, but several omitted important financial/history observations, and both prompts proposed the wrong expected payout for the below-deductible task.

The longer oracle checklist prompt did not beat the baseline on that small single-model sample. Both strategies had zero complete strict passes on the four reserved tasks because required observations were missing. That result does not mean every declared assertion was wrong; it means the generated cases did not fully satisfy the explicit rubric.

The preserved sensitivity demonstration makes the practical consequence visible: narrow reviewed cases missed two known ledger/history faults, while strengthened reviewed cases detected both. The AI explanation demonstration also contained contradictory wording and weak secondary citations. V5 links the raw records so you can discuss those weaknesses instead of presenting AI prose as established cause.

Codex implemented the framework. Local Ollama actually generated the preserved proposals and explanation. ChatGPT, Copilot and Claude Code have optional, concrete learning exercises, but were not silently connected or claimed to have run. VS Code remained in its observed workspace trust mode; Copilot availability and account setup are the user's choices.

## 14. How to use and explain the finished project

Start with README, then follow docs/V5_DEMO.md. The recommended eight-minute narrative goes from written rules and expected payout to a persisted workflow, then AI proposal/review, quality measurements, raw investigation facts and the release rehearsal. Finish with the actual private repository Actions result and this report.

For implementation learning, inspect showcase.py and the API hooks, then release.py and rehearse.py. Identify the trust boundaries: user/demo identity, unapproved model output, explicit reviewer attestation, disposable execution, archived source, sidecar manifest and mutable release state. Explain what each boundary checks and what remains an assumption.

For a second-assistant exercise, supply a synthetic contract and narrow test and ask which observation is missing. Independently derive the expected value and implement only a reviewed suggestion. Do not use agreement between assistants as a substitute for a written reference and observed evidence.

The final architecture narrative is in docs/ARCHITECTURE.md, with a diagram of the three paths: deterministic claims, reviewed AI testing and release evidence. The operating commands and failure boundaries are in docs/OPERATIONS.md. Each earlier version still has its own report, so you can read why complexity was added in stages.

## 15. Limits and outcome

This is a professional learning and demonstration framework with verified finite workflows. It uses invented plan contracts, demo role selectors and local reviewer labels. It does not implement real Medicare or commercial benefit adjudication, authenticated users, patient-data handling, production authorization, financial transactions or regulatory certification.

The local release manager is single-operator tooling. Atomic pointer replacement does not provide distributed orchestration, coordinated multi-process deployment or zero-downtime service replacement. Per-release state isolation is not a database rollback/migration policy for a live payer platform. The provider and background comparison jobs remain local and bounded rather than a durable multi-worker AI service.

The authored evaluation set is small and visible for learning. Its reserved results are no longer fresh after first use. Valid schemas, exact citation IDs, passing tests and consistent checksums each establish different limited facts. The framework's value is making those facts inspectable and their limitations explicit.

Across five versions we achieved an independent project with written contracts, deterministic tests, stateful workflows, actual reviewed local AI generation, measured proposal weaknesses, source-assisted investigation, a guided showcase and reproducible local releases. The final GitHub and rehearsal records establish which delivery actions actually ran. Further public hosting would be a new scoped deployment decision, not an assumed final checkbox.

## 16. Evidence and reproduction commands

```sh
python3 -m tools.bootstrap --browser
.venv/bin/python -m tools.verify
.venv/bin/python -m tools.serve --port 8895
```

After verification, build and inspect a candidate without overwriting a delivered release:

```sh
.venv/bin/python -m tools.release build --output .local/candidates/my-candidate
.venv/bin/python -m tools.release inspect .local/candidates/my-candidate/v5.0.0-source.zip
.venv/bin/python -m tools.rehearse .local/candidates/my-candidate/v5.0.0-source.zip --baseline releases/v4.0.0-source.zip
```

Read artifacts/v5/verification.json, deployment-rehearsal.json, github-ci.json and preservation-check.json, together with the source/manifest files under releases. V4 live model records remain in artifacts/v4. Exact artifact availability is shown in the guided showcase; a missing record is not labeled complete.

## 17. Primary technical references

Waitress documents running a WSGI application with explicit host and port configuration. The project chooses loopback and a bounded thread count rather than the library's default network binding. [Waitress usage](https://docs.pylonsproject.org/projects/waitress/en/stable/usage.html).

Python documents ZIP handling and path-related extraction considerations. This project implements explicit member/root/type/digest checks and writes only validated members into a new staging tree. [Python zipfile](https://docs.python.org/3/library/zipfile.html).

GitHub documents workflow artifacts as files shared or retained from workflow runs. This project's workflow uploads the source bundle, manifest and execution evidence after its stages. [GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts).

The earlier reports retain the Ollama, pytest and Playwright references behind their respective implementations. The delivery evidence is our own observed execution, not a quotation from those technical documents.
