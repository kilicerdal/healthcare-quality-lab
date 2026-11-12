# Lesson 3 — AI creates a proposal, not truth

Open the AI Test Studio and inspect a real saved workflow proposal. Its actions and expected responses were produced by local Ollama, not selected from the project's golden examples.

## Understand the boundaries

The model receives the requirement, selected rule text, synthetic plan/member/actor fixtures and a schema. It returns JSON with cases, steps and expectations. Python checks the structure and permitted actions. That protects execution boundaries; it does not prove the model understood the business rule.

## Read a generated case

A step has an action, actor, data and expect. A submit step might expect status 201, claim_status submitted and revision 1. A later duplicate submission expects status 409 and error DUPLICATE_CLAIM. Read the exact input IDs: steps within one case share state, while the next case starts clean.

Ask whether the assertions actually cover the requirement. A case that reaches paid status but never asserts payment_cents does not prove the ledger amount is right. V3's real model output demonstrated this omission. The engineering example added explicit money and history expectations while preserving the original generation.

## Make a correction

Enter a reviewer label and a note explaining the independent expected result. Open the JSON editor, change the case and save. Previous approval disappears because it described a different data snapshot. Select cases again, check the attestation and save the new review. Review labels are not authenticated identity or proof that a human has understood the test.

## Run and interpret

The runner compares each declared expectation with an observed service projection and records both. A failing case can mean an application defect, an incorrect generated expectation or a misunderstood contract. Inspect the evidence before changing the application. V3 does not automatically declare the model's explanation correct or repair code.

## Use pytest

After approval, download the trusted pytest wrapper. It embeds the reviewed data as a safely encoded JSON string, checks hashes/contracts and runs the same controlled runner. The model did not author the executable wrapper. Run it in this project with pytest; the exported cases are parametrized individually.

## Your exercise

Generate a payout case, check the arithmetic yourself, then inspect a workflow case for missing payment/history assertions. Explain why schema validity and a passing narrow test are both insufficient evidence of complete requirement coverage.
