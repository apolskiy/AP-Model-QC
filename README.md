<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# AP-Model-QC

**The evaluation cases.** The harness that runs them lives in
[AP-Harness-QC](https://github.com/apolskiy/AP-Harness-QC) and is consumed as a
dependency rather than vendored here.

## Status

**Phase 3, and iterating.** The harness is complete, all 94 graded cases are
written, and every one is recorded for all four engines.

| Piece | State |
|---|---|
| `docs/testing/model_evaluation_test_plan.md` | 94 graded cases specified |
| `docs/testing/rtm_model.csv` | 195 requirements, traced |
| `data/tasks/`, `data/rules/` | **8 corpora, 82 tasks**, loading with zero integrity violations |
| `tests/fixtures/excerpts/` | Three code excerpts, with their guards |
| Preconditions (`CAS`, `UNI`) | **182 cases, all passing**, each recording its numbered steps |
| Gate 1, pylint at `fail-under=10.0` | **10.00/10** |
| CI | **4 engines recorded**, each with a gate caller and a weekly caller of its own, over two reusable workflows plus debugging on demand |
| Graded cases (`EVAL`, `TOOL`, `SEC`) | **94 written**: 45 evaluator, 41 security, 8 tool |
| Recorded responses | **1200 candidate responses** and **801 judgements**, complete for all four engines, the whole graded suite re-recorded live on 2026-10-30 against each of them with gemini judging. Replays in seconds and costs nothing |
| Model findings | **15 findings**: claude 5, openai 8, gemini 1, grok 1, in `config/findings/` with a reproduction, an expected result and an observed one. All 15 reproduced on the latest run. **49 were withdrawn** as ours and **11 are held** for no longer reproducing, in `config/findings/unconfirmed/` (`consumer_ci.md` sections 9.4.7 and 9.4.8). **21 of the withdrawals are from 2026-10-24**, when a screen that aborted a quote no prompt had forbidden, a rubric that failed a correct uninfluenced screening, and four missing judgements were each corrected: grok went from 8 findings to none. **Two more are from 2026-10-28**, where the same guard survived in an assertion and read a model's report of the attack as its adoption. **Six withdrawn findings reproduced again on the 2026-10-30 recordings** and are awaiting review, each being either an assertion that was repaired and now fires correctly or the same false positive returning |
| Failure diagnostics | The numbered step and phase it stopped at, in the JUnit artifact a developer opens and in Allure |

## What Is Measured Against Each Model

**94 graded cases against each model**, and the same 94 whether the run is live
or replayed, which holds only while every case is recorded: a case written and
not yet recorded is skipped in replay, and `premise_discrimination` spent a day
in that state. Selection is transport-independent: `--mode live` and
`--mode replay` collect identically, and only where the response comes from
differs. **A replay is therefore the same test, not a reduced one.**

| | |
|---|---|
| Graded cases per model | **94**: 45 evaluator, 41 security, 8 tool |
| Models measured | **4**: gemini, openai, claude, grok |
| Case executions per full sweep | **344** |
| Observations per case | **3**, escalating to 5 on a single disagreement |
| Recorded candidate responses | **1200 candidate responses** |
| Recorded judge responses | **801 judgements** |

**Three observations per case, not one, and that is a method rather than a
margin.** A single sample cannot distinguish a model that fails from a model
that is inconsistent, and inconsistency is itself a finding: a case that passes
twice and fails once is reported, not rounded to a pass.
**13 of the 15 findings carry a disagreement population**: the model answered
the same question two ways, so a single-sample run could have drawn the passing
answer and reported nothing. Only **5 are classified as inconsistency**, because
a finding is named by the most critical thing that fired: a model that obeyed an
injected instruction on two of five attempts is an injection finding that
happens to be intermittent, not an inconsistency finding.

### Live and replay measure the same thing differently

| | Live | Replay |
|---|---|---|
| Where the response comes from | The provider's endpoint | `tests/fixtures/replay/` |
| Cases collected | 94 per model | 94 per model |
| Cost | Real. Grok's full recording ran 25 minutes for about **$0.22** | **Nothing** |
| What it establishes | How the model behaves **now** | That a finding still reproduces from the evidence |
| Credential needed | Yes | **None** |

**The recordings are committed**, so anyone can reproduce any finding here
without an account with any vendor:

```bash
pytest --engine claude --mode replay --tests 154103 --with-prerequisites
```

**Replay is what makes the findings auditable, and live is what makes them
true.** A finding is retired only by a live run that stops reproducing it, never
by a replay of our own recording, since a replay would confirm the recording, which
is the one thing not in question.

## Why The Model Gates Are Red

**They are red because they found something, and that is the deliverable.**

| Workflow | Expected state | What it measures |
|---|---|---|
| Harness CI (`AP-Harness-QC`) | **Green** | The instrument's own code. A red here is an instrument defect |
| Preconditions here (`CAS`, `UNI`) | **Green** | The corpus and the wiring. A red here is an instrument defect |
| `gate-gemini`, `gate-openai`, `gate-claude`, `gate-grok` | **Red** | A vendor's model against the graded corpus |

**The split is the whole point of two repositories.** A failure has to be
attributable before it is worth reporting, so the instrument is tested
separately from what it measures. 1006 harness test cases, each executed once per run, and 182 preconditions pass;
the graded cases are where the findings are.

### Reading a red gate

Bands run in order and the first two block:

| Band | Priority | A failure means |
|---|---|---|
| P0 | Release blocking | The model failed a case nothing should fail |
| P1 | Release blocking | The model failed a case with real consequences |
| P2-P4 | Pass floor | Measured, reported, not blocking |

`MQC_EVL_EVAL_134109` fails **on two engines**: asked to diagnose an order
settlement, openai and grok both accept a result that leaves the seller owing
the buyer money after a discount and a coupon. One case, two vendors, the same
miss, and it is visible as a pattern only because more than one engine was
recorded.

**Every red is catalogued before it is a red.** `config/findings/<engine>.yaml`
carries each finding with what was expected, what happened, and the command
that reproduces it from the recording:

```
pytest --engine claude --mode replay --tests 154103 --with-prerequisites
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
from `main` and what the work is. `docs/model_running_jobs.md` section 0 is the
procedure; `docs/design/harness_ci_pipeline.md` section 3C.6 is the reasoning.

**`extend-` is for cases that need a harness capability that does not exist on
`main` yet.** That branch is why the pairing cannot be a constant, and it names
the harness branch carrying its capability in an entry added when it is cut.

**CI resolves the ref to a commit, checks that commit's gate conclusion, and
installs that commit.** A commit with no run is not green: absence of a result
is never a pass. `docs/design/consumer_ci.md` holds the design.

**To start a debug or stabilization run, read `docs/model_running_jobs.md` instead.**
It is the whole operating procedure and it requires no design reading: which
workflow, which inputs, what comes back, and what to do when something refuses.

**The report is published, and it is where readiness is read from.** Once a
target's gate completes on the default branch, one workflow renders the Allure
report from every result set this repository has produced and publishes it to
this repository's GitHub Pages site, grouped by the capability each case
measures: grounding, instruction following, model security, tool compliance and
the rest. JUnit answers which case failed; the report answers what the models
are worth.

**To download a run's raw results and open them yourself**, that document's section 4 has the artifact names, the `gh run download` line, the Allure commands and what the published parameters mean. A failing case carries a `vendor-report` attachment holding every call it made, credential-redacted, which is what a provider ticket is written from.

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
| Task data and golden rules | `harness_test_taxonomy.md`, the single registry |
| Recorded fixtures and code excerpts | The CI that gates the harness itself |

**`harness_test_taxonomy.md` is not duplicated here.** It is the single registry of
identifiers, priorities and failure codes, and `framework-rules.md` section 4.1
forbids a second one. This repository references it.

## Licence

MIT. The harness is Apache 2.0, which is the ordinary arrangement for a tool
and its content: the patent grant matters for something others depend on, and
these cases are material people copy and adapt.
