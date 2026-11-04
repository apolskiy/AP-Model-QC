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

Nothing. The re-record of the two repaired gates closed on 2026-11-04: all four
engines are recorded live, each replays identically, the register is reconciled
and every figure that moved is in `CHANGELOG.md`.


## Waiting

| Item | Waiting on |
|---|---|
| Two withdrawn findings reproduced again on the 2026-11-04 run, claude `134101` and `134308`, and carry review tickets | A ruling per finding, which only the project owner can give: each is a decision about this project's own assertion rather than about the model. The three that carried a mark from 2026-11-01 passed on this run and `clear_stale_reproductions` dropped it |
| `A_SEC_HIDDEN_NO_QUOTE_*` accounts for ten of the corpus's twenty-one failures, every matched span being two or three words of ordinary English such as "full match" or "instructions and" | A ruling on whether the decision of 2026-10-30 still prices correctly. It chose this error over passing an answer that quoted, and the test plan recorded the cost in advance; what is new is the size of it, on answers the judge scores 5 of 5 for reporting the injection the case asks them to report |
| 64 recordings are observation 3 or 4 of a case that escalated to five in an earlier run and took three in this one | A decision on whether a live run prunes observations above the new escalation, which is the recording half of the judgement question already open in the harness. They are inert while the three fresh observations agree, and a later escalation would read a previous run's answers into a fresh inconsistency verdict with nothing reporting it |
| openai is pinned to `gpt-4.1` and every recording resolves `gpt-4.1-2025-04-14`, April 2025, while the other three resolve current models | A ruling on whether to move the pin. Five of the nine genuine findings, a P0 among them, characterise that model rather than OpenAI's current one, and the openai entry is the only one of the four carrying no dated rationale |
| Every `evaluate-*` caller defaults `max_spend` to `2.00`, and a full live sweep measured $3.37 of candidate spend on claude alone | A ruling on the ceiling, which is a spending decision rather than a defect. Dispatched at its own default, a claude sweep stops partway and reports a partial measurement as though the selection had been measured; the four weekly callers reserve a schedule they do not yet use, so the dispatch path is the only one this reaches |
