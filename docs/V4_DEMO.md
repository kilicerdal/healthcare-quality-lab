# V4 demonstration — approximately 8 minutes

Open the standalone folder in VS Code and the local application at http://127.0.0.1:8894/#evaluation.

1. Show evaluation_v4.json: four development tasks, four reserved tasks, literal expectations and sources.
2. Select the saved development comparison. Explain schema validity versus strict task pass. D02 has a wrong oracle; D03 lacks meaningful observations.
3. Select the saved held-out comparison. Both strategies have 0/4 strict passes despite correct comparable declared assertions. Explain missing fields and the unscored H04 extra.
4. Retrieve WF-004 and inspect the returned contract and rank. Explain that lexical matches can be weak.
5. Select the saved investigation. Read the code-extracted 91000-versus-90000 fact, then identify the model's contradiction. Do not infer an established cause from its prose.
6. Open assertion-sensitivity.json and show the already-reviewed snapshots: 0/2 versus 2/2 detection for two known faults.
7. Show verification.json: 297 tests passed; explain deterministic provider doubles versus 17 separate live calls.
8. Open the detailed report. Explain that local showcase and CI configuration are delivered, while remote Actions and production deployment remain unexecuted.

Optional: start a new comparison with only D01 and observe persisted progress. This makes two new local model requests and creates unapproved drafts. No comparison runs a draft.
