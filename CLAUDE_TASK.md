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

Nothing. The live run on the flagships closed on 2026-11-06: openai and gemini
recorded again, every judgement made again on `gemini-4-argon`, and every
failure examined (`CLAUDE_LOG.md`, same date). What it leaves is under Waiting.


## Waiting

| Item | Waiting on |
|---|---|
| gemini `134106`: all five observations answer line 2 and add, unqualified, that the interpreter reports line 3, which CPython 3.14 does not. Three pass and two fail on incidental hedge words | The owner's ruling on whether that claim is a hallucination. Then the rule changes if needed, all four engines are replayed, and the findings and tickets are regenerated |
| grok `134201`, withdrawn 2026-11-06 as judge variance (identical requests scored 5, 5 and 2), fails again on the same recordings and carries a review ticket | The owner's ruling on the review ticket |
| gemini `134206`, a confirmed finding, and `134106` once ruled | Filing with the vendor from `reports/tickets/` |
| `134106` to `134108` on openai, and any dependent whose foundation fails | Ruled 2026-11-05: CI does not run a dependent whose foundation failed, so a dependent needing a recording is recorded here, outside CI, one at a time |
| Observations above a pair's new count | Ruled 2026-11-05: a live run outside CI updates the observations of a modified or new case, or one made stale by a major harness change; `record_fixture` already retires a pair's observations whose request changed (harness `tier2_execution.md` section 7.14). Observations of an unchanged request are not stale and are kept |
