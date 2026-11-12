# V4 implementation plan

Work only in `/Users/erdalkilic/Documents/Healthcare Quality Lab`. V3's source archive and evidence are verified and preserved.

## Build

1. Version an eight-task authored evaluation dataset with development and reserved held-out splits. Keep scoring answers out of model prompts.
2. Define a deterministic rubric for input/action matching, expected-value correctness and required-assertion completeness. Do not execute unapproved proposals during scoring.
3. Freeze paired prompt/task inputs before comparison jobs, retain raw drafts, and record failures and denominators honestly.
4. Add lexical source retrieval with explicit scores and source IDs; no vector-store claim.
5. Extract observed facts from recorded runs, then ask local Ollama for cited hypotheses that can abstain. Do not let model prose overwrite facts or execute repairs.
6. Measure whether already-approved raw versus strengthened cases detect selected seeded faults; never use unapproved drafts as executable tests.
7. Add a browser Evaluation & investigation workbench, regression tests, live local experiments and versioned evidence.
8. Deliver a detailed V4 report explaining design, outcomes, limitations and V5's remaining scope.

## Limits

References are authored and engineering-checked, not learner-reviewed or a statistical certification. The reserved split is held out of prompt tuning, not unknown to its author. Outputs from its first run expose the answers; reruns must be labeled reused. ID-valid citations do not prove that an AI hypothesis is true.
