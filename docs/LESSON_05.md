# Lesson 5 — Explain and reproduce your release

1. Start the showcase. Distinguish health, readiness, test verification and model evaluation; explain why none alone proves production readiness.
2. Run the full verifier and inspect the source fingerprint. Edit a disposable copy of a tracked file and explain why its old result becomes stale; restore that copy before testing again.
3. Inspect a source archive and its sidecar. Explain the difference between a checksum and a trusted digital signature.
4. Read tools/release.py. Follow validation, temporary staging, file verification, activation pointer and rollback. Identify why state is outside the payload.
5. Inspect the recorded V4→V5 rehearsal. Explain why rollback preserves V4 data while V5 records remain separate.
6. Open the actual GitHub Actions run. Locate dependency install, Chromium setup, verification, packaging, HTTP rehearsal and uploaded evidence. Compare local rollback scope with CI's current-package scope.
7. Ask a second assistant to critique one narrow assertion or the release validation. Provide only synthetic examples. Independently check its proposed change and run the relevant tests.

## Multi-tool practice prompts

For ChatGPT or another conversational assistant: “Given this synthetic contract and test, list missing observable assertions and derive each expected value. State assumptions; do not invent payer rules.”

For Copilot in your editor: “Propose a pytest for this failure path using existing fixtures. Explain what defect it would detect and avoid mirroring implementation.” Review its diff and run the focused test before keeping it. The current VS Code Restricted Mode may keep Copilot disabled; decide workspace trust yourself.

For Claude Code or another repository assistant: “Review the release staging and rollback code. Identify a concrete integrity failure and show how to reproduce it without touching other projects.” Keep its findings separate from verified evidence.

These are optional learning exercises, not integrations or execution claims. Codex and the recorded local Ollama runs are the AI tools actually evidenced in this delivery.
