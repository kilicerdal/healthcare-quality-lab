# AI tools learning playbook

The purpose is to learn how to brief, inspect and evaluate different AI tools. Give them the same synthetic requirement and evaluate their work against the same contract. A larger tool count does not establish higher test quality.

## V1 tool status

- Codex: used to implement V1, explain its design, run tests and assess local-model suggestions.
- Ollama with qwen2.5:3b: actually used for a local contract review. Raw response, prompt, token counts, settings and timing are in `artifacts/ai-review.json`.
- ChatGPT: a prepared requirements and test-design exercise; no separate ChatGPT session or API call was executed by this implementation.
- GitHub Copilot: a prepared editor exercise; no Copilot-generated change was executed or counted as delivered work.
- Claude Code: a prepared independent review exercise; no Claude Code run was executed or counted as delivered work.

## Common task and scoring

Use HC-007 and its explicit fixture values. Ask for positive, boundary and negative cases. For each suggestion, record its tool/model when available, the prompt, expected response, source rule, any unsupported assumption, whether it duplicates an existing case, the reviewer's correction and the final observed result. Judge correctness before counting test ideas.

The actual V1 Ollama review illustrates an error: it suggested denying a claim equal to the payout cap. The contract approves it after deductible subtraction. Its below/at-deductible ideas largely overlap existing examples. The engineering assessment is not a completed learner approval.

## ChatGPT exercise

Paste HC-007 from `healthcare_quality/data/rules.json`, not any patient information, and ask:

```text
Explain this synthetic software contract in plain English. Propose five boundary tests with explicit inputs and expected decisions and payouts. Distinguish claim amount from payout cap. List assumptions. Do not add real Medicare rules. Do not infer that a missing example means the project lacks a test. I will review each proposal before using it.
```

Compare its proposed values with the golden examples. Ask it to explain one disagreement. Preserve the original response and your correction rather than silently replacing it.

## GitHub Copilot exercise in VS Code

After your own Copilot account and extension are available, open `claims.py`, `rules.json`, and `test_claims.py` as context. Use an ask/review mode first:

```text
Read HC-007 and the existing tests. Identify one untested boundary without changing implementation code. Explain the independent expected result. Suggest a pytest test, but wait for my review before editing files. Work only in Healthcare Quality Lab.
```

Review a proposed test before adding it. Run it on the reference and consider which faulty variant it should detect. A generated test that merely repeats production calculations may miss the same defect.

Official workflow: https://docs.github.com/en/copilot/tutorials/write-tests

## Claude Code exercise

If Claude Code is installed and authenticated, start it in this project only. Request a bounded read-only review:

```text
Review only this Healthcare Quality Lab project. Do not edit or inspect neighboring projects. Read the synthetic contracts and tests. Identify an incorrect assertion, a missing risk case, or an unsupported coverage assumption. Cite exact files and rules. Distinguish observed defects from hypotheses. Do not run paid external APIs or change the contracts to make tests pass.
```

Judge findings against the same evidence. An additional model is an additional reviewer, not independent proof. Save useful findings in a project-local note after reviewing them.

Official workflow: https://code.claude.com/docs/en/common-workflows

## Ollama exercise

```sh
python -m tools.ai_review --model qwen2.5:3b
```

The model must already be installed and the local service running. The script has a timeout, output budget, response-size cap, JSON checks and source-ID validation. It has no execution tools and cannot approve tests. `artifacts/ai-review.json` is replaced on each run, so copy an experiment to a separately named file if you want to preserve multiple comparisons.

Official API: https://docs.ollama.com/api/generate

## Codex exercise

Ask Codex to explain a single existing test, show the written requirement behind its expected result, and identify a mutation it should catch. Keep all requested changes inside this project. For larger changes, ask for the concrete acceptance criteria before implementation, then inspect the diff and test evidence.

## Learning record template

Tool and model:

Requirement and prompt:

Proposed test and expected result:

Unsupported assumptions or duplicate coverage:

Reviewer correction and explanation:

Executed result and evidence path:

What I can now explain without the tool:

V3 will bring structured AI-generated test proposals into the application itself. These V1 exercises do not provide that workflow yet.

## V2 workflow review exercise

V2 actually used local `qwen2.5-coder:3b` to review WF-001 through WF-006. Its output and assessment are stored separately in `artifacts/v2/`. It suggested unknown-actor, duplicate and repeated-approval checks that already existed, while incorrectly calling their contracts unspecified. No suggestion was counted as a novel code contribution.

For ChatGPT, Copilot or Claude Code, ask for an independent read-only review of `workflow.py`, `workflow_rules.json` and `test_workflow.py`. Ask specifically whether a ledger failure can leave a paid status, and require exact evidence. These remain exercises until you actually run them with your accounts. Do not grant a coding tool access to neighboring projects as context for this task.

## V3 actual test creation

V3 actually generated new declarative test cases using both local qwen2.5-coder:3b and qwen2.5:3b during development. It did not select tests from the golden catalog. Raw attempts, blocked output, corrections, review attestations and live execution are preserved under artifacts/v3.

Use the same acceptance brief with ChatGPT, Copilot or Claude Code as a learning exercise, but do not call those integrations executed until you actually use them. Compare source relevance, input types, expected values, assertion completeness and reviewer corrections. Current live attempts differ in schema/prompt and are not a controlled model comparison.
