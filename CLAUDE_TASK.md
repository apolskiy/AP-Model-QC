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

Nothing. The last item closed on 2026-11-01, when `115797` stopped reading
`reports/` and generated the tickets it checks.


## Waiting

| Item | Waiting on |
|---|---|
| The no-quote rules separate the engines by how a disclosure is worded rather than by whether the model resisted | A ruling on whether a function-word run such as the one measured on claude counts as reuse of the planted passage. Measured over all 120 recorded observations of the eight rules: gemini fails none and claude fails 36 of its 40 recordings |
| Three withdrawn findings reproduced again on the 2026-11-01 run and carry review tickets | A ruling per finding, which only the project owner can give: each is a decision about this project's own assertion rather than about the model |
