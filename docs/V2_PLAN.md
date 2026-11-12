# V2 implementation plan

Project: `/Users/erdalkilic/Documents/Healthcare Quality Lab` only.

V1 source and evidence are preserved in `releases/v1.0.0-source.zip` and `artifacts/v1/` before changes.

## What we will build

1. Synthetic members, policies and named demo actors; ownership and role rules live on the server.
2. SQLite persistence for claims, status history and a simulated payment ledger.
3. Customer submission, adjuster approval and finance payment: submitted → approved → paid.
4. Duplicate-ID protection, rejected-submission cleanup, atomic state changes and single ledger entries.
5. An interactive workflow desk with actor selection, claim detail, timeline and evidence export.
6. Reusable API test helpers and Playwright page objects; isolated databases for every test.
7. Expanded healthcare scenarios, workflow defect experiments and recorded verification.
8. A detailed V2 report covering purpose, architecture, decisions, outcomes, AI review and limits.

## Explicit boundaries

Demo actor selection simulates roles; it is not login or production authorization. All members, benefit rules and ledger entries are synthetic. No real payment, patient data, external payer call or deployment is involved. AI-generated executable tests remain V3.

## Acceptance

Existing covered behavior remains passing. Positive and negative workflows preserve state correctly. Concurrent duplicate submissions create one claim; concurrent payment attempts create one ledger entry. Tests use disposable temporary databases, not the interactive database. Saved evidence links workflow requirements to results.
