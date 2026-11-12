# Local release operations

## First run

Use Python 3.13 for the environment verified in this delivery. `python3 -m tools.bootstrap --browser` creates a project-local virtual environment if absent, installs pinned dependencies and optionally Chromium. `--dry-run` prints the exact commands. `--runtime-only` omits pytest and Playwright. It never deletes an existing environment or downloads Ollama models.

Start `python -m tools.serve --port 8895`. The default state is this project's `.local`. It binds only 127.0.0.1 through Waitress with eight threads. AI generation can occupy a thread for up to 90 seconds; this is a local single-process showcase, not a horizontally scaled service.

## Verify and package

Run `python -m tools.verify`. Check status passed, zero failures/skips and a matching source fingerprint. Then run `python -m tools.release build`. An existing release filename is never overwritten. For a candidate use `--output .local/candidates/UNIQUE_LABEL`.

The sidecar manifest records version, SHA-256 archive digest, source fingerprint, per-file digests and verification counts. Inspect with `python -m tools.release inspect ARCHIVE`. The validator rejects a changed archive, member digest mismatch, unsafe paths, symlinks, duplicate members, excluded sensitive/local paths, and expansion above 256 MiB. This protects consistency, not publisher authenticity; accept a manifest only from a trusted source.

## Stage, activate and serve

`python -m tools.release stage ARCHIVE` creates an immutable-named payload under `.local/deployments/releases`. The ID includes version and the archive hash prefix. A temporary staging directory is validated before rename. Use the returned ID with `python -m tools.release activate RELEASE_ID`. Activation rechecks every staged file and atomically replaces current.json, retaining the previous pointer.

`python -m tools.release serve --port 8896` rechecks the selected release before starting its packaged app with the current environment's Waitress. The state directory is `.local/deployments/state/RELEASE_ID`, outside the payload. Runtime dependencies must already be installed. The package is source, not a self-contained interpreter.

Stop the current server with Ctrl+C before changing releases. Activation changes a pointer for the next launch; it does not replace a running server. `python -m tools.release rollback` activates the previous verified payload, then start serve again. Each release uses its own state. State is retained when switching away and returning; this does not migrate or synchronize records across versions. Do not use these commands for real healthcare data.

## Readiness and request evidence

`/api/health` reports process response/version. `/api/ready` attempts to open the three expected databases and query their expected tables. It does not contact Ollama, prove write availability or certify production readiness. Storage unavailability returns 503. Request responses include X-Request-ID and Server-Timing; structured application records contain method, route pattern, status and duration, omitting query strings, headers and payloads.

The V4 provider remains fixed to loopback port 11434, bounded to a 256 KiB envelope and 90-second request timeout. The comparison budget is soft, checked between requests. There is no cloud fallback. Successful runs, stale contracts and missing source evidence can abstain from investigation.

## Rehearsal

`python -m tools.rehearse ARCHIVE --baseline releases/v4.0.0-source.zip` stages both actual archives, boots each through Waitress, exercises payout/ownership/duplicates/approval/payment/ledger/history, rolls back and checks earlier state, then reactivates the new release and checks its state. Evidence is written under artifacts/v5. No model inference occurs.

CI omits the baseline flag because historical ZIPs are retained locally rather than tracked in Git. Its rehearsal validates the current source package's HTTP journey. Local evidence separately demonstrates rollback. Do not conflate those scopes.

## Remote CI and deployment

The private GitHub Actions workflow needs only contents:read. It uploads release/evidence artifacts after testing. It does not connect to a production host, publish a public endpoint or ship model downloads. A cloud target would require a separate design for authentication, storage, secrets, private model access, operational ownership and deployment approval.
