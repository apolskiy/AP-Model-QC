<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# AP-Model-QC

**The evaluation cases.** The harness that runs them lives in
[AP-Harness-QC](https://github.com/apolskiy/AP-Harness-QC) and is consumed as a
dependency rather than vendored here.

## Status

**Phase 3, and iterating.** The harness is complete, all 69 graded cases are
written, and the security family is recorded in full and passing against a
paid tier.

| Piece | State |
|---|---|
| `docs/testing/model_evaluation_test_plan.md` | 69 graded cases specified |
| `docs/testing/rtm_model.csv` | 101 requirements, traced |
| `data/tasks/`, `data/rules/` | **7 corpora, 65 tasks**, loading with zero integrity violations |
| `tests/fixtures/excerpts/` | Three code excerpts, with their guards |
| Preconditions (`CAS`, `UNI`) | **86 cases, all passing** |
| Gate 1, pylint at `fail-under=10.0` | **10.00/10** |
| CI | **4 engines recorded**, each with a gate caller and a weekly caller of its own, over two reusable workflows plus debugging on demand |
| Graded cases (`EVAL`, `TOOL`, `SEC`) | **69 written**: 40 evaluator, 21 security, 8 tool |
| Recorded responses | **812 candidate responses** and **415 judgements**, complete for all four engines. Replays in seconds and costs nothing |
| Model findings | **24 findings** — gemini 2, openai 8, claude 10, grok 4 — each with a reproduction, an expected result and an observed one, in `config/findings/` |

## What Is Measured Against Each Model

**69 graded cases against each model**, and the same 69 whether the run is live
or replayed. Selection is transport-independent: `--mode live` and
`--mode replay` collect identically, and only where the response comes from
differs. **A replay is therefore the same test, not a reduced one.**

| | |
|---|---|
| Graded cases per model | **69** — 40 evaluator, 21 security, 8 tool |
| Models measured | **4** — gemini, openai, claude, grok |
| Case executions per full sweep | **276** |
| Observations per case | **3**, escalating to 5 on a single disagreement |
| Recorded candidate responses | **812 candidate responses** |
| Recorded judge responses | **415 judgements** |

**Three observations per case, not one, and that is a method rather than a
margin.** A single sample cannot distinguish a model that fails from a model
that is inconsistent, and inconsistency is itself a finding: a case that passes
twice and fails once is reported, not rounded to a pass.
**14 inconsistency findings** of the 24 are visible only because of it: more
than half, and none of them reachable by a single-sample run.

### Live and replay measure the same thing differently

| | Live | Replay |
|---|---|---|
| Where the response comes from | The provider's endpoint | `tests/fixtures/replay/` |
| Cases collected | 69 per model | 69 per model |
| Cost | Real. Grok's full recording ran 25 minutes for about **$0.22** | **Nothing** |
| What it establishes | How the model behaves **now** | That a finding still reproduces from the evidence |
| Credential needed | Yes | **None** |

**The recordings are committed**, so anyone can reproduce any finding here
without an account with any vendor:

```bash
pytest --engine grok --mode replay --tests 134205
```

**Replay is what makes the findings auditable, and live is what makes them
true.** A finding is retired only by a live run that stops reproducing it, never
by a replay of our own recording — a replay would confirm the recording, which
is the one thing not in question.

## Why The Model Gates Are Red

**They are red because they found something, and that is the deliverable.**

| Workflow | Expected state | What it measures |
|---|---|---|
| Harness CI (`AP-Harness-QC`) | **Green** | Our own code. A red here is our defect |
| Preconditions here (`CAS`, `UNI`) | **Green** | Our corpus and our wiring. A red here is our defect |
| `gate-gemini`, `gate-openai`, `gate-claude`, `gate-grok` | **Red** | A vendor's model against the graded corpus |

**The split is the whole point of two repositories.** A failure has to be
attributable before it is worth reporting, so the instrument is tested
separately from what it measures. 691 harness cases and 84 preconditions pass;
the graded cases are where the findings are.

### Reading a red gate

Bands run in order and the first two block:

| Band | Priority | A failure means |
|---|---|---|
| P0 | Release blocking | The model failed a case nothing should fail |
| P1 | Release blocking | The model failed a case with real consequences |
| P2–P4 | Pass floor | Measured, reported, not blocking |

`MQC_EVL_EVAL_134205` fails at P1 **on all four engines**: a case where the
model overstates a figure its source does not support. Four vendors, four
failures, one case — which is a finding about the task being hard rather than
about any one provider, and it is visible only because more than one engine was
recorded.

**Every red is catalogued before it is a red.** `config/findings/<engine>.yaml`
carries each finding with what was expected, what happened, and the command
that reproduces it from the recording:

```
pytest --engine grok --mode replay --tests 134205
```

That command needs no credential and spends nothing. **The recordings are in
the repository**, so a reader can reproduce any finding here without an account
with any vendor.

### Why they are not quarantined

A quarantine mechanism would mark a known finding as expected and turn the
gates green, so that a red meant something new. **It is deliberately not built
yet.** These findings are being filed with each vendor, and a gate that reports
them is the evidence; quarantining them before they are filed would hide the
result this project exists to produce. The mechanism is designed in
`consumer_ci.md` section 4.19.4 and its trigger is recorded there.

**The weekly live ladders are a separate matter and stay unscheduled**, because
a cron that is always red for reasons recorded days earlier communicates
nothing. Section 4.18.3 holds that reasoning.

## Why This Is A Separate Repository

Split from the harness on 2026-09-23, closing A17. One repository made a commit
a version of the harness **and** the cases together, so neither could move
without the other and CI could not answer whether a case set still passed
against the previous harness.

| Capability | One repository | Now |
|---|---|---|
| A case set runs against a chosen harness version | No | Yes, the pairing is an input |
| Harness and cases version independently | No, one commit is both | Yes |
| Roll back cases without reverting harness fixes | No | Yes, or either, or both |
| A harness change re-verified against every case set | Not expressible | Yes, fan out across consumers |

The reasoning, the rejected alternative and the verified split boundary are in
`AP-Harness-QC`, `DESIGN.md` section 5.1.

## Which Harness A Branch Runs Against

**The pairing is per branch, and it is data.** `config/harness_pin.yaml` maps a
branch of this repository to the harness ref it runs against, because a run is
defined by a pair of refs and one pin cannot state a pairing for every branch.

| This branch | Runs against | Green required |
|---|---|---|
| `main` | harness `main` | **Yes.** A non-green harness refuses the run |
| `stabilization-<referent>-<date>` | Its own entry, or harness `main` | No, the run proceeds ungated |
| `expand-<referent>-<date>` | harness `main` | No |
| `extend-<referent>-<date>` | Its own entry, or harness `main` | No |
| `debug-<referent>-<date>` | harness `main` | No |

**Branches are dated and carry a referent**, which is the day they were cut
from `main` and what the work is. `docs/running_jobs.md` section 0 is the
procedure; `docs/design/ci_pipeline.md` section 3C.6 is the reasoning.

**`extend-` is for cases that need a harness capability that does not exist on
`main` yet.** That branch is why the pairing cannot be a constant, and it names
the harness branch carrying its capability in an entry added when it is cut.

**CI resolves the ref to a commit, checks that commit's gate conclusion, and
installs that commit.** A commit with no run is not green: absence of a result
is never a pass. `docs/design/consumer_ci.md` holds the design.

**To start a debug or stabilization run, read `docs/running_jobs.md` instead.**
It is the whole operating procedure and it requires no design reading: which
workflow, which inputs, what comes back, and what to do when something refuses.

**To download a run's results and view them**, that document's section 4 has the artifact names, the `gh run download` line, the Allure commands and what the published parameters mean. A failing case carries a `vendor-report` attachment holding every call it made, credential-redacted, which is what a provider ticket is written from.

## Pinning A Harness Version

The harness reference is an **input**, which is the whole point of the split.
A case set declares what it was verified against:

```bash
python -m pip install "ap-harness-qc @ git+https://github.com/apolskiy/AP-Harness-QC@main"
```

Swap `@main` for a tag, a stabilization branch, or a commit to run these cases
against a different harness. That is how a regression is attributed: hold the
cases fixed and move the harness, or the reverse.

## What Lives Here, And What Does Not

| Here | In the harness |
|---|---|
| Graded cases: `EVAL`, `TOOL`, `SEC` | The four modules and their precondition suites |
| `model_evaluation_test_plan.md`, `rtm_model.csv` | Every module design, `harness_test_plan.md`, `rtm_harness.csv` |
| Task data and golden rules | `test_taxonomy.md`, the single registry |
| Recorded fixtures and code excerpts | The CI that gates the harness itself |

**`test_taxonomy.md` is not duplicated here.** It is the single registry of
identifiers, priorities and failure codes, and `framework-rules.md` section 4.1
forbids a second one. This repository references it.

## Licence

MIT. The harness is Apache 2.0, which is the ordinary arrangement for a tool
and its content: the patent grant matters for something others depend on, and
these cases are material people copy and adapt.
