<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# AP-Model-QC

**The evaluation cases.** The harness that runs them lives in
[AP-Harness-QC](https://github.com/apolskiy/AP-Harness-QC) and is consumed as a
dependency rather than vendored here.

## Status

**Phase 3, and iterating.** The harness is complete and all 95 graded cases are
written. Every one is recorded for all four engines except `134207`, written on
2026-11-05 and not yet recorded, and `134203` and `134402`, whose prompts
changed that day and whose recordings answer the old ones.

| Piece | State |
|---|---|
| `docs/testing/model_evaluation_test_plan.md` | 95 graded cases specified |
| `docs/testing/rtm_model.csv` | 215 requirements, traced |
| `data/tasks/`, `data/rules/` | **8 corpora, 83 tasks**, loading with zero integrity violations |
| `tests/fixtures/excerpts/` | Three code excerpts, with their guards |
| Preconditions (`CAS`, `UNI`) | **210 cases, 209 passing**, each recording its numbered steps. **`115804` is red** until the 222 stored judgements made without the system instruction are judged again |
| Gate 1, pylint at `fail-under=10.0` | **10.00/10** |
| CI | **4 engines recorded**, each with a gate caller and a weekly caller of its own, over two reusable workflows plus debugging on demand |
| Graded cases (`EVAL`, `TOOL`, `SEC`) | **95 written**: 46 evaluator, 41 security, 8 tool |
| Recorded responses | **1170 candidate responses** and **728 judgements**, complete for all four engines, with gemini judging. **The whole graded suite was re-recorded live against all four engines on 2026-11-04**, after a prompt asking for a list began being checked for that list, and the cases whose prompt or rule changed during the review that followed were recorded again, with the cases depending on them. **Every case on every engine holds a recording made on or after 2026-11-04, except openai `134106` to `134108`**, recorded on 2026-11-03 and skipped behind `134203` in every openai run since. **Held for re-recording since 2026-11-05**: `134203` and `134402`, whose prompts changed, and `134207`, which has no recording; and the 222 judgements of tasks carrying a system instruction, 208 of the hidden-passage cases and 14 of `gnd_no_falsehood`, invalid because their judge was not shown it. Replays in seconds and costs nothing |
| Model findings | **13 findings**: openai 8, grok 3, claude 2, gemini 0, in `config/findings/` with a reproduction, an expected result and an observed one. **Reconciled against the sweep of 2026-11-04** and the reruns after it. **48 are withdrawn** as ours, one withdrawal having been reopened on 2026-11-04 and since held, and **33 are held** for no longer reproducing, in `config/findings/unconfirmed/` (`consumer_ci.md` sections 9.4.7 and 9.4.8). **21 of the withdrawals are from 2026-10-24**, when a screen that aborted a quote no prompt had forbidden, a rubric that failed a correct uninfluenced screening, and four missing judgements were each corrected: grok went from 8 findings to none. **Two more are from 2026-10-28**, where the same guard survived in an assertion and read a model's report of the attack as its adoption. **No withdrawn finding is awaiting review**: openai's `134400` reproduced in the sweep of 2026-11-04 and passed when recorded again the same day, which clears the mark (`consumer_ci.md` section 9.5.5.12) |
| Failure diagnostics | The numbered step and phase it stopped at, in the JUnit artifact a developer opens and in Allure |

### Models tested, and the judge

**The harness pinned by `config/harness_pin.yaml` names the model each engine
runs**, its provider's flagship, confirmed before every live run outside CI. On
2026-11-05 openai and gemini moved, and the judge with gemini, so the recordings
of those two engines and every judgement are made again in the live run.

| Engine | Model the next live run uses | Model the stored recordings answer |
|---|---|---|
| openai | `gpt-6-astra` | `gpt-4.1-2025-04-14` |
| claude | `claude-opus-5-5` | `claude-opus-5-5` |
| gemini | `gemini-4-argon` | `gemini-3.8-flash` |
| grok | `grok-4.7` | `grok-4.7` |
| **Judge** | **gemini, `gemini-4-argon`** | **gemini, `gemini-3.8-flash`** |

## What Is Measured Against Each Model

**95 graded cases against each model**, and the same 95 whether the run is live
or replayed, which holds only while every case is recorded: a case written and
not yet recorded is skipped in replay, and `premise_discrimination` spent a day
in that state. Selection is transport-independent: `--mode live` and
`--mode replay` collect identically, and only where the response comes from
differs. **A replay is therefore the same test, not a reduced one.**

| | |
|---|---|
| Graded cases per model | **95**: 46 evaluator, 41 security, 8 tool |
| Models measured | **4**: gemini, openai, claude, grok |
| Case executions per full sweep | **344** |
| Observations per case | **3**, escalating to 5 on a single disagreement |
| Recorded candidate responses | 1170, which is 284 to 302 per engine: **a model that answers inconsistently is sampled more, so it is recorded more** |
| Recorded judge responses | 728, which is 176 to 190 per engine: a rule that authors no rubric is judged by nobody, and an observation that fails an assertion never reaches the judge |

**Three observations per case, not one, and that is a method rather than a
margin.** A single sample cannot distinguish a model that fails from a model
that is inconsistent, and inconsistency is itself a finding: a case that passes
twice and fails once is reported, not rounded to a pass.
**9 of the 13 findings carry a disagreement population**: the model answered
the same question two ways, so a single-sample run could have drawn the passing
answer and reported nothing. Only **5 are classified as inconsistency**, because
a finding is named by the most critical thing that fired: a model that obeyed an
injected instruction on two of five attempts is an injection finding that
happens to be intermittent, not an inconsistency finding.

### Live and replay measure the same thing differently

| | Live | Replay |
|---|---|---|
| Where the response comes from | The provider's endpoint | `tests/fixtures/replay/` |
| Cases collected | 95 per model | 95 per model |
| Cost | Real, and measured per engine over every observation a full run dispatches: about **$0.57** on openai, **$0.74** on gemini, **$1.31** on grok and **$3.32** on claude, or **$5.93** for all four | **Nothing** |
| What it establishes | How the model behaves **now** | That a finding still reproduces from the evidence |
| Credential needed | Yes | **None** |

**What those figures are.** Each is the candidate's own bill, priced from the
token counts the provider reported for every stored observation, plus the
judge's bill estimated from the stored prompt and reply at four characters per
token. The judge costs between $0.13 and $0.16 whichever engine is measured,
because gemini judges every run. Claude is five times gemini because its output
rate is 20.00 per million tokens and its thinking is billed inside that output,
and grok's bill is dominated by input, 420,886 tokens of which 376,576 were
served from cache.

**The cheapest engine is not the cheapest to measure.** Openai holds 324
observations and claude 320 against grok's 298 and gemini's 296, because a disagreement
escalates a case from three samples to five: a model that answers inconsistently
is asked more often, and the method charges for that.

**A ceiling is set above the whole figure, and it counts the candidate half
only.** `--max-spend 2.00` stopped a claude sweep on 2026-11-02 at 50 of its 94
cases; 8.00 is the figure these measurements support, and the judge's bill sits
outside whatever is set.

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
separately from what it measures. 1056 harness test cases, each executed once per run, and 209 of 210 preconditions pass;
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
