# V8 observation adapter contract

## Contract v1

A test case is the existing validated benefit DSL. Each step has an allowlisted action, teaching actor, bounded data, and a complete expected observation. The runner validates before starting a target and compares built-in types as well as values; `true` cannot satisfy an expected integer `1`.

An implementation supplies `execute(cases, target)` and returns per-case pass/fail plus per-step field assertions. Every case receives fresh state. The installed registry accepts only `application` and `reference_peer`; it never accepts a model-provided URL or command.

Application adapter: existing actual HTTP endpoints `/api/benefits/claims` and their fixed lifecycle actions, persisted SQLite, full raw responses, request IDs and independent expected observations.

Reference peer: separate loopback HTTP server with `/contract/v1/step`, strict action schema, a lock around independent in-memory lifecycle state and projected observations. This uses the same independent oracle that authors expected values. It proves protocol portability and runner integration, not an additional independent proof of the oracle. It has no claim database or production pricing imports. It is a teaching target, not a real third-party payer.

## Adding a real system

Implement its authentication, request mapping, response normalization, isolation/reset strategy, request budgets and sanitized evidence retention in a reviewed adapter. Add it to the trusted registry in source. Write contract tests for missing fields, malformed JSON, errors, duplicate operations and type mismatches. Never obtain expected financial results by recording that system's response. Run explicit contract and negative tests before authorizing real data or nonlocal execution. No such external connection was added in V8.
