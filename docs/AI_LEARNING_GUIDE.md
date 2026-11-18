# AI tools: actual use and optional exercises

The implementation uses Codex for engineering, local Ollama for explicit model proposals/evaluations, and GitHub Actions to run the deterministic and opt-in local-model workflows. pytest, Playwright, independent references and SQLite provide verification; they are not AI models. The interview deck is an editable companion artifact. No new paid API call is part of V6.3–V6.7.

The existing optional OpenAI evaluation CLI and spending controls remain unchanged. Installing a different assistant or writing an exercise is not evidence that its output was evaluated. Do not present ChatGPT, Copilot or Claude Code as measured integrations unless you actually run them and retain the output.

## Repeatable comparison exercise

Use one frozen synthetic requirement with each assistant you have access to. Ask for a bounded benefit case matching the supplied schema. Retain the exact prompt and original response, label the tool/model/version and date, and import the result as an unapproved proposal. Keep any manually constructed wrapper labeled authored. Record invalid schema, wrong values, missing observations, changed scenarios and duplicates. Use the same independent gate for every tool. Do not give an oracle answer in the raw phase.

An optional second request may include reference feedback. Store it separately as assisted output. Never edit the original answer and call the revised result raw model performance. Do not infer quality from one convincing response or combine correlated repeats as independent samples.

## Provider-neutral prompts to learn with

**Requirements critique:** “Review this invented benefit rule. List ambiguities, boundary cases and missing facts. Do not invent real coverage policy. Separate questions from proposed assumptions.” This can be used as a ChatGPT exercise or with another available assistant.

**Editor assistance:** “Propose one regression case in the supplied DSL that fails when the ledger amount is wrong. Explain its independent expected value. Do not modify application pricing to make the test pass.” This is an optional Copilot exercise; no editor was opened during this implementation.

**Alternate review:** “Inspect the proposed case, frozen inputs and independent report. Identify unsupported assumptions, missing readbacks and stale approvals. Do not approve or execute it.” This is an optional Claude Code exercise or a review by another assistant.

**Local evaluation:** use `tools.advanced_evaluate` with installed Ollama models. Unlike the optional exercises above, the release retains actual bounded local-model measurements and their failures.

Accounts, subscriptions and credential access remain operator-controlled. Never put credentials, real member data or real claims into source-controlled artifacts. The lab's synthetic fixtures let you learn the workflow without needing those inputs.
