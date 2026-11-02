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
| Three withdrawn findings reproduced again on the 2026-11-01 run and carry review tickets | A ruling per finding, which only the project owner can give: each is a decision about this project's own assertion rather than about the model |
| Three repaired gates leave openai `134400` and `134109` and grok `134408` skipping, their newly passing observations asking for judgements the store does not hold | A live judge pass through `--fill-gaps` on those three cases, which spends judge quota and writes fixtures. `consumer_ci.md` section 9.4.10 carries what a replay measured; no candidate call is owed, the prompts being unchanged |
| openai is pinned to `gpt-4.1` and every recording resolves `gpt-4.1-2025-04-14`, April 2025, while the other three resolve current models | A ruling on whether to move the pin. Five of the nine genuine findings, a P0 among them, characterise that model rather than OpenAI's current one, and the openai entry is the only one of the four carrying no dated rationale |
