# V3 controls and acceptance criteria

These controls govern AI test proposals. HC/WF contracts remain the independent domain reference; a valid citation ID does not prove semantic grounding.

| Control | Required behavior | Primary evidence |
| --- | --- | --- |
| AI-CTL-001 | Generation uses only a fixed loopback Ollama endpoint and allowed installed model names; no fixture/cloud fallback | Provider tests and saved live request metadata |
| AI-CTL-002 | Cases must satisfy JSON Schema, allowed actions/fields, selected sources, IDs, duplicate and observable checks | Schema/adversarial unit tests |
| AI-CTL-003 | Generation persists raw output and leaves cases unapproved with no execution | Unit/API/browser tests |
| AI-CTL-004 | Review requires a label, note, unique valid selections and explicit expectation-check attestation | Review-gate tests |
| AI-CTL-005 | Edits and review decisions advance revision; edits clear approval; stale updates are rejected | Revision and browser correction tests |
| AI-CTL-006 | Execution/export require matching current contract/schema and approved case hashes | Stale-contract, tamper and export tests |
| AI-CTL-007 | Cases use separate temporary SQLite stores, at most 32 actions, and stop on first mismatch | Runner isolation and failure evidence |
| AI-CTL-008 | Prompt, raw response, settings, reviews, changes and expected/observed assertions remain inspectable | Persisted experiment exports |
| AI-CTL-009 | Model and execution failures are explicit; ordinary execution exceptions do not strand a running record | Provider and runner failure tests |
| AI-CTL-010 | Exported pytest is fixed trusted wrapper code around reviewed JSON data, not model-authored code | Wrapper execution and browser download tests |

Input scope: generated action amounts are integer cents in the supported bounded range, flags are booleans, IDs and services are short strings. Invalid-type payload tests remain in the independent pytest suite; not every arbitrary malformed request can be expressed in this first DSL.

Quality warnings flag proposed assumptions and missing payout/payment/event assertions when their relevant rules are cited. They do not establish completeness, source relevance or correct arithmetic. Reviewers remain responsible for checking the oracle.

Generation has a 90-second request timeout, 2600-token output setting, 12288-token context setting and 256 KiB response-envelope cap. One generation is permitted at a time per service instance. A runner deadline is checked between actions; it is not a hard process kill. An abrupt process exit can leave a generating/running record requiring a new experiment; automatic crash recovery is deferred.
