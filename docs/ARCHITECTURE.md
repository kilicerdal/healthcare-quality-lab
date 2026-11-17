# Final architecture narrative

The system has three evidence paths sharing written synthetic contracts.

## Current provider and proof boundaries

```mermaid
flowchart LR
  Browser[Engineering proof browser] --> API[Loopback Flask API]
  API --> Proof[Authored isolated proof scenarios]
  Proof --> Temp[(Disposable SQLite state)]
  Browser --> Results[Recorded provider comparison]
  CLI[Explicit paid evaluation CLI] --> Budget[(Persistent reservation ledger)]
  Budget --> OpenAI[OpenAI Responses API]
  Local[Explicit local evaluation CLI] --> Ollama[Loopback Ollama]
  OpenAI --> Proposed[Unapproved expectations and calculations]
  Ollama --> Proposed
  Proposed --> Reference[Independent reference checks]
  Reference --> Results
```

The proof page executes authored controls, not model calls. Provider comparison data is read-only in the browser. Live evaluation is a separate explicit CLI path; its budget ledger and credentials do not enter browser assets or the source bundle. Model output is neither approved nor executed automatically. Proof scenarios isolate temporary state; the separate claim desk may retain its own synthetic database.

```mermaid
flowchart TD
  C[Written synthetic contracts] --> E[Python evaluator]
  E --> W[Transactional claim workflow]
  W --> A[Flask API and browser desk]
  C --> P[Versioned prompt and schema]
  P --> O[Local Ollama]
  O --> D[Unapproved declarative drafts]
  D --> G[Validation and explicit review]
  G --> R[Hash-bound approved snapshot]
  R --> T[Disposable service runner]
  D --> Q[Reference comparison without execution]
  T --> F[Code-extracted observed facts]
  F --> H[Retrieved rules and AI hypotheses]
  A --> V[pytest and Playwright verification]
  V --> B[Checksummed source bundle]
  B --> S[Validated local staging]
  S --> L[Atomic activation and rollback]
```

The evaluator checks invented eligibility/benefit/network/authorization/formulary/deductible/limit contracts. The workflow owns member identity, state transitions, event history and simulated ledger writes inside SQLite transactions.

Studio metadata is separate from claims. Raw proposals never become executable code. Review binds selected data hashes and the current contract fingerprint. Each approved case executes in a disposable database; the browser desk uses persistent synthetic state. The downloaded pytest wrapper is trusted application-authored code containing reviewed data.

V4 compares drafts to authored reference data without executing them. It freezes prompt/task inputs and keeps all raw results. Investigation extracts runner failures in code before any model call. Valid citation IDs do not prove an explanation is true.

V5 verifies implementation/configuration fingerprints, packages source and portable synthetic evidence, validates payload digests and paths, and stages isolated releases. Activation/rollback changes an atomic pointer, with state separated per release. Waitress serves the selected payload on loopback. There is no distributed queue, hot deployment or database migration. GitHub Actions verifies the same code on Ubuntu and rehearses the newly built package over actual HTTP.

All five versions are learning milestones in one independent project. Earlier archives preserve earlier implementations; the current checkout contains V5. Public healthcare eligibility, real claims processing, patient data, external payments and production access control remain outside the system.
