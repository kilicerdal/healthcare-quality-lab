# V3 demonstration guide

## Prepare

Start the existing local Ollama service with one of the allowed installed models. Start V3 using the README command and open `http://127.0.0.1:8893/#ai`. The core regression suite can run without Ollama; a real generation cannot.

## Real generation

Choose HC-007 and describe a synthetic payout scenario. Select Check Ollama, then Generate. Show the model, prompt hash, raw response, settings, token counts, validation findings and exact source contract. Explain that generation created drafts and did not run them.

For a workflow request, choose WF-002, WF-003, WF-004, WF-005 and HC-007. Ask for duplicate submission and a full approval/payment lifecycle. Inspect each actor, claim ID and expected result. The existing saved real workflow experiment is still unapproved for learner review.

## Review and correction

Read the proposed oracle. If a payment case omits payment_cents or event_count, explain the gap. Fill a reviewer label/note, edit the case JSON, and save. Show that previous approval is invalidated. Select valid cases, attest that expectations were checked and save the review. A local attestation is not production authentication.

## Isolated execution

Run the approved snapshot. Inspect every expected/observed field. Explain that the runner calls Python services in new temporary databases, not the interactive claims store or arbitrary generated code. Export the full experiment JSON.

## Python tests

Download the approved pytest wrapper. Inspect its fixed Python code and embedded reviewed data. Save it under tests/generated if you want it included in future local pytest discovery, then run it. The delivered live wrapper under artifacts/v3 can be run separately using the README command.

## Evidence already recorded

The initial real generation contained invalid observations and an incorrect payout. Later generations included wrong types, prose in a reason-code field and missing monetary/history assertions. All attempts are retained. The final raw workflow cases passed their narrow assertions; engineering corrections added the missing oracle checks and were re-reviewed before a second run. Those demonstrations used disposable experiment copies and did not approve the user's original records.

V4 will add broader evaluation datasets and grounded investigation. Do not present these few live requests as a model-quality benchmark or a comparison of model superiority.
