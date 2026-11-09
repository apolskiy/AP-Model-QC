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
| The filing sheet of 2026-11-08: gemini `134206` as a warning | Ruled 2026-11-07: nothing is filed until the project is complete, and each ticket is first confirmed to be the model's fault, not the harness's or the case's. claude's `154103` was the case's and is converted (`CLAUDE_LOG.md`, same date); `134206` is reviewed next |
| `134106` to `134108` on openai, and any dependent whose foundation fails | Ruled 2026-11-05: CI does not run a dependent whose foundation failed, so a dependent needing a recording is recorded here, outside CI, one at a time |
| Observations above a pair's new count | Ruled 2026-11-05: a live run outside CI updates the observations of a modified or new case, or one made stale by a major harness change; `record_fixture` already retires a pair's observations whose request changed (harness `tier2_execution.md` section 7.14). Observations of an unchanged request are not stale and are kept, except one beyond a first pass that holds, which `115820` reports (`consumer_ci.md` section 6.4.7) |
