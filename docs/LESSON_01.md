# Lesson 1 — Understand one rule and one assertion

Start with `tests/unit/test_claims.py::test_deductible_is_subtracted`.

The synthetic requirement HC-007 says to subtract the plan deductible, never pay a negative amount, then cap the payout at the plan limit. In this fixture, the claim is 100000 cents ($1,000), the deductible is 10000 cents ($100), and the payout cap is 200000 cents ($2,000). The expected payout is therefore 90000 cents ($900).

```python
result = evaluate_claim({
    "plan_id": "commercial_ppo",
    "service": "medical",
    "amount_cents": 100000,
})
assert result["payout_cents"] == 90000
```

`evaluate_claim` is the code under test. The explicit number `90000` is our expected result, derived from the written requirement. `assert` tells pytest to fail when the observed result differs. We do not calculate the expected result by calling the production function a second time: that would reproduce its own mistakes.

Run this one check:

```sh
python -m pytest tests/unit/test_claims.py::test_deductible_is_subtracted -v
```

Next inspect `test_claim_equal_to_cap_is_approved_after_deductible`. The actual local model suggested that a claim equal to the payout cap should be denied. The contract says otherwise: 200000 - 10000 = 190000 cents, so it is approved with that payout. This shows why a fluent AI answer needs a test oracle.

## How the layers connect

The unit test calls Python directly. API tests send JSON to Flask's in-process HTTP test client. Playwright starts Chromium, fills the real browser form, sends an actual HTTP request to a temporary local server, and checks the displayed result. All three layers exercise the same rule at different boundaries.

## Your exercise

Before running anything, predict the outcomes for amounts 9999, 10000, 10001, 200000 and 300000 cents. Explain the difference between claim amount and payout cap. Compare your predictions with the written contract and the existing tests. No source modification is needed for this exercise.

A passing test confirms one assertion under specified conditions. It does not prove all coverage is correct or that the framework satisfies an exam syllabus.
