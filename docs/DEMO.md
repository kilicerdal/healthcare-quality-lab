# V1 five minute demonstration

## Prepare

Open Healthcare Quality Lab in VS Code. Run `python -m tools.verify` to refresh evidence. Start the app with the V1 debug launch or the README command. Open `http://127.0.0.1:8891`.

## 1 Explain the purpose

Say: “This is a synthetic healthcare testing lab. V1 establishes explicit rules and independent tests so later AI output can be evaluated.” Point to the eight plan contracts, seven rules, seventeen service categories and recorded verification.

## 2 Observe a covered claim

Load scenario 01. Evaluate the $1,000 commercial PPO claim. Show the $900 payout and HC-007 calculation. Explain that the $100 deductible and $2,000 cap are invented per-evaluation fixtures.

## 3 Observe a denial and correct it

Load scenario 02. Evaluate the Advantage hospital fixture without authorization. Show AUTH_REQUIRED and HC-005. Check Authorization received and evaluate again. Show the changed decision without changing the claim amount.

## 4 Inspect a coverage contract

Open Coverage explorer, filter Medicare and show four configurations. Explain that Advantage is Part C, not an additional part. Open the rulebook and read HC-003. Load scenario 03 to show a Part D dental denial in the fixture.

## 5 Show evidence and defect detection

Export the evaluation JSON. In VS Code, show `artifacts/defect-benchmark.json`. Explain each seed is a deliberately authored faulty variant and that all seven are detected against a passing reference. Avoid calling this exhaustive mutation coverage.

## 6 Show AI learning

Open `artifacts/ai-review.json` and `artifacts/ai-review-assessment.json`. Explain how a real local model incorrectly proposed denial at the payout cap. Show the independent regression assertion that preserves HC-007. Valid JSON is not proof of correct reasoning.

## Close with the next milestone

Open the roadmap and identify V2 as the next planned version. Do not present later AI generation, persistent claims, remote CI or deployment as already implemented.
