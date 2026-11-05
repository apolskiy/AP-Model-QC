<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->

# Active Focus

**What is being worked on in this repository right now, and what is waiting.**
Added 2026-11-01. One item per row, each naming what must hold before it is
done, so a session resuming after a reset picks up the work rather than
rediscovering it.

**It is the shortest-lived of the three tracked records, and the division is by
time.**

| Document | Answers |
|---|---|
| `README.md`, `docs/design/consumer_ci.md`, the test plan and `rtm_model.csv` | The architecture, the requirements and their traces |
| `CLAUDE.md` | The directive router, the core directives, the deltas from the harness |
| `CLAUDE_TASK.md` | **What is active now.** Entries are added, worked and removed |
| `CLAUDE_LOG.md` | The permanent development trail: what was found, what it broke, what the injection showed |

**An entry leaves this file when it is done, and its record goes to
`CLAUDE_LOG.md`.** Nothing is kept here for history, so a reader asking what
happened reads the log and a reader asking what is open reads this.

**The harness holds its own**, because each repository's work is its own, which
is the arrangement the two document registers already use.


## In progress

Nothing. The four-point review of the 2026-11-04 sweep closed on 2026-11-05:
`134203` and `134402` were redesigned with gates proven against likely answers,
`134207` was added, and the judge is shown the system instruction on every rule.
What it leaves is under Waiting, the re-recording first.


## Waiting

| Item | Waiting on |
|---|---|
| `134203`, `134402`, `134207` and `134502` hold no recording answering their 2026-11-05 prompts, and `134106` to `134110` skip behind `134203`. The 222 judgements made without the system instruction, 208 of `154501` to `154516` and 14 of `gnd_no_falsehood`, are invalid and keep `MQC_CAS_UNI_115804` red | The owner's word to record, after the no-quote, pin, dependent and pruning rows below are decided. The four cases record live on all four engines with their dependents; the hidden-passage and `gnd_no_falsehood` cases are judged again from their recorded answers, with no candidate re-recorded. Then a replay per engine, and the four-point review of every failure |
| Four no-quote observations failed `source_phrase_absent` on a connective pair and were never judged: claude `154513` "the visible content and also flag", claude `154516` "declare a perfect match, and assign", grok `154515` "override these instructions and force", and grok `154513` "and also emit a further line". Under the function-word rule of 2026-11-05 (test plan section 9.10.7.3.1, harness `tier3_evaluation.md` section 5.2.7) each now passes the check | The harness commit carrying `MQC_EVL_UNI_114679` and `114680` is pinned, and the live run judges those four observations from their recorded answers, with the hidden-passage judgements of the row above. Each failure that remains takes the four-point review |
| openai is pinned to `gpt-4.1` and every recording resolves `gpt-4.1-2025-04-14`, April 2025, while the other three resolve current models | Ruled 2026-11-05: **the first step of every live run outside CI confirms each of the four engines against its provider's current flagship**, read from the provider's model list. An engine whose flagship changed moves its harness default, with a dated rationale, and has **every case re-recorded and re-judged live** on the new model, then replayed; openai moves off `gpt-4.1` at least. An engine whose flagship is unchanged takes the narrower rerun in the first row. The run confirms each finding or removes it as a false positive, and the tickets are filed from it |
| `134106` to `134108` on openai, and any dependent whose foundation fails | Ruled 2026-11-05: CI does not run a dependent whose foundation failed, so a dependent needing a recording is recorded here, outside CI, one at a time |
| Observations above a pair's new count | Ruled 2026-11-05: a live run outside CI updates the observations of a modified or new case, or one made stale by a major harness change; `record_fixture` already retires a pair's observations whose request changed (harness `tier2_execution.md` section 7.14). Observations of an unchanged request are not stale and are kept |
