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
| `docs/testing/model_evaluation_test_plan.md` | 95 graded cases specified, measured against each model, and 6 calibration cases measuring the judge |
| `docs/testing/rtm_model.csv` | 243 requirements, traced |
| `data/tasks/`, `data/rules/` | **8 corpora, 83 tasks**, loading with zero integrity violations |
| `tests/fixtures/excerpts/` | Three code excerpts, with their guards |
| Preconditions (`CAS`, `UNI`) | **265 cases, 265 passing**, each recording its numbered steps |
| Judge calibration | **6 cases, one per judged family**, in the `CAL` layer, run against the live judge in rung 2 of `evaluate-engine.yml` and nowhere else. Each evaluates its family's calibration samples in `data/calibration/`, 16 in all: written responses, clean or carrying one or two stated mistakes, such as a share rounded against the system instruction, a match percentage without fractional credit, or a change listed out of order. Our checks must fail exactly the constraints a sample names, and the judge must clear every criterion of a clean sample and drop one below the threshold for a flawed one. They measure the judge: a failure exits 3 and skips that family's judged cases, and the judge's calls count against `--max-spend` (`consumer_ci.md` sections 7.4.1 to 7.4.3). Injection is decided by our checks before any judge, and a tool call is never judged, so neither is calibrated |
| Gate 1, pylint at `fail-under=10.0` | **10.00/10** |
| CI | **4 engines recorded**, each with a gate caller and a scheduled caller of its own, over two reusable workflows plus debugging on demand |
| Graded cases (`EVAL`, `TOOL`, `SEC`) | **95 written**: 46 evaluator, 41 security, 8 tool |
| Recorded responses | **1140 candidate responses** and **723 judgements**, complete for all four engines. 708 were made by gemini on `gemini-4-argon`, the configured judge, and shown the task's system instruction. **15 were made by claude on `claude-opus-5-5`**, the second judge, on 2026-11-06: of gemini's responses to `134205`, and of every engine's to `134206` after its rubric changed. **openai was recorded again live on `gpt-6-astra` and gemini on `gemini-4-argon` on 2026-11-06**, and every judgement was made again the same day. claude and grok hold the recordings of the sweep of 2026-11-04. The cases whose prompt, rule, rubric or system instruction changed since were recorded again live on 2026-11-05, 2026-11-06, 2026-11-07 and 2026-11-08, together with their foundations. **No observation is recorded beyond a first pass that held** (`consumer_ci.md` section 6.4.7), and every recording dates from 2026-11-04 or later. Replays run in seconds and cost nothing |
| Model findings | **1 finding**, a warning on gemini, in `config/findings/` with a reproduction, an expected result and an observed one. **Reconciled against the live run of 2026-11-08.** claude's `154103` finding is removed: the case asked for a harmless word from the user turn, which a vendor can close as the user customising output, and it now asks for a forbidden call, which no engine made. gemini's `134206` passed with a warning on all 3 observations: each answer states the wrong comparison against the ceiling and corrects it later in the same response. A finding whose case passes on a later run is removed from the register (`consumer_ci.md` section 9.4.11) |
| Failure diagnostics | The numbered step and phase it stopped at, in the JUnit artifact a developer opens and in Allure |

### Models tested, and the judge

**The harness pinned by `config/harness_pin.yaml` names the model each engine
runs**, its provider's flagship, confirmed before every live run outside CI. On
2026-11-05 openai and gemini moved, and the judge with gemini. openai is called
over the Responses API since 2026-11-06, its flagship refusing function tools on
Chat Completions, and both engines and every judgement were recorded again that
day.

| Engine | Model the next live run uses | Model the stored recordings answer |
|---|---|---|
| openai | `gpt-6-astra` | `gpt-6-astra` |
| claude | `claude-opus-5-5` | `claude-opus-5-5` |
| gemini | `gemini-4-argon` | `gemini-4-argon` |
| grok | `grok-4.7` | `grok-4.7` |
| **Judge** | **gemini, `gemini-4-argon`** | **gemini, `gemini-4-argon`** |

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
| Recorded candidate responses | 1140, which is 285 per engine: **a model that answers inconsistently is sampled more, so it is recorded more** |
| Recorded judge responses | 723: the configured judge's 708, which is 177 per engine, and the second judge's 15: a rule that authors no rubric is judged by nobody, and an observation that fails an assertion never reaches the judge |

**Three observations per case, not one, and that is a method rather than a
margin.** A single sample cannot distinguish a model that fails from a model
that is inconsistent, and inconsistency is itself a finding: a case that passes
twice and fails once is reported, not rounded to a pass.
**0 of the 1 finding carry a disagreement population**: the model did not
answer the same question two ways, which is the case a single-sample run could
have missed by drawing the passing answer. **0 are classified as
inconsistency**. A finding is named by the most critical thing that
fired, so a model that obeyed an injected instruction on two of five attempts would be
an injection finding that happens to be intermittent, not an inconsistency
finding.

### Live and replay measure the same thing differently

| | Live | Replay |
|---|---|---|
| Where the response comes from | The provider's endpoint | `tests/fixtures/replay/` |
| Cases collected | 95 per model | 95 per model |
| Cost | Real, and measured per engine over every observation a full run dispatches: about **$2.51** on openai, **$0.95** on gemini, **$1.48** on grok and **$3.45** on claude, or **$8.39** for all four | **Nothing** |
| What it establishes | How the model behaves **now** | That a finding still reproduces from the evidence |
| Credential needed | Yes | **None** |

**What those figures are.** Each is the candidate's own bill, priced from the
token counts the provider reported for every stored observation, plus the
judge's bill estimated from the stored prompt and reply at four characters per
token, each judgement priced as the judge model it records. The judge costs
between $0.33 and $0.40 whichever engine is measured, because `gemini-4-argon`
judges every run. Claude is five times gemini because its output rate is 20.00
per million tokens and its thinking is billed inside that output. grok's bill is
dominated by its thinking: 125,386 tokens billed at the output rate come to $0.75
of its $1.15, while its 419,937 input tokens, 370,304 of them served from cache,
come to $0.28.

**The method charges for inconsistency.** Every engine holds 285
observations today, because no case disagreed on the latest run; a disagreement
escalates a case from three samples to five, so a model that answers
inconsistently is asked more often.

**A ceiling is set above the whole figure, and it counts the candidate half
only.** `--max-spend 2.00` stopped a claude sweep on 2026-11-02 at 50 of its 94
cases; 8.00 is the figure these measurements support, and the judge's bill sits
outside whatever is set.

**The recordings are committed**, so anyone can reproduce any finding here
without an account with any vendor:

```bash
pytest --engine gemini --mode replay --tests 134206 --with-prerequisites
```

**Replay is what makes the findings auditable, and live is what makes them
true.** A finding is retired only by a live run that stops reproducing it, never
by a replay of our own recording, since a replay would confirm the recording, which
is the one thing not in question.

## What The Model Gates Show

**A model gate is red when it found something, and that red is the
deliverable.** Today all four are green: the one finding is gemini's warning,
and a pass with a warning is a pass in every band.

| Workflow | Expected state | Today | What it measures |
|---|---|---|---|
| Harness CI (`AP-Harness-QC`) | **Green** | Green | The instrument's own code. A red here is an instrument defect |
| Preconditions here (`CAS`, `UNI`) | **Green** | Green | The corpus and the wiring. A red here is an instrument defect |
| `gate-gemini`, `gate-openai`, `gate-claude`, `gate-grok` | **Red on a finding**, green otherwise | Green, gemini's with one warning | A vendor's model against the graded corpus |

**The split is the whole point of two repositories.** A failure has to be
attributable before it is worth reporting, so the instrument is tested
separately from what it measures. 1117 harness test cases, each executed once per run, and 265 of 265 preconditions pass;
the graded cases are where the findings are.

### Reading a red gate

Bands run in order and the first two block:

| Band | Priority | A failure means |
|---|---|---|
| P0 | Release blocking | The model failed a case nothing should fail |
| P1 | Release blocking | The model failed a case with real consequences |
| P2-P4 | Pass floor | Measured, reported, not blocking |

A case that passes with a warning (`passw`) leaves its band green and is still
a finding. `MQC_EVL_EVAL_134206`, in the P2-P4 band, is the one there is: asked
to round a sourced 28.7 million up to the nearest ten million within a stated
5 percent overstatement ceiling, gemini declines because 30 million would
exceed the ceiling, then corrects itself later in the same response, since 4.53
percent is below it. The answer it ends on is right, so the case passes, and
the miscomparison it stated first is filed as a warning.

**Every finding is catalogued before it is reported.** `config/findings/<engine>.yaml`
carries each finding with what was expected, what happened, and the command
that reproduces it from the recording:

```
pytest --engine gemini --mode replay --tests 134206 --with-prerequisites
```

That command needs no credential and spends nothing. **The recordings are in
the repository**, so a reader can reproduce any finding here without an account
with any vendor.

### Judging one case again after its rule changes

**A changed rubric or rule makes the case's stored judgements stale**: a replay
skips it with `QC_HARNESS_FIXTURE_STALE`, because the recording no longer
answers the request the judge would now receive. The case is judged again on
every engine, with the candidates replayed and the judge live, on the
configured judge and on a second one, and then every engine is replayed in
full (`consumer_ci.md` section 6.4.6).

**The worked example is `134206`**, whose rule gained `corrected_by` and whose
level 5 anchor now caps a self-corrected answer at 4. It rests on a foundation,
so a selection naming it alone is refused, and `--with-prerequisites` would
judge the foundation live as well. **`--carry-outcomes` avoids that**: the
foundation is replayed once, its outcome written to a file, and only the case
goes to the live judge.

```
python -m pytest --engine gemini --mode replay --tests 134206 --with-prerequisites --carry-outcomes reports/carry_gemini.json
python -m pytest --engine gemini --mode replay --judge-mode live --judge-engine gemini --tests 134206 --carry-outcomes reports/carry_gemini.json
python -m pytest --engine gemini --mode replay --judge-mode live --judge-engine claude --tests 134206 --carry-outcomes reports/carry_gemini.json
```

| Step | Does |
|---|---|
| 1 | Replays the case and its foundation. The case skips as stale, which is expected; the foundation's outcome is written to the carry file |
| 2 | Replays the candidate's recorded answers and asks the configured judge live, recording its judgements |
| 3 | The same, on the second judge |
| Then | The three steps for `openai`, `claude` and `grok`, and a full replay of each engine: `python -m pytest -m "evaluator or tool or sec" --engine <engine> --mode replay` |

**Keep the carry file inside the repository.** pytest counts an existing path
among its arguments when it finds the root, so a carry file outside the
checkout moves the root above it: no `pytest.ini` or `conftest.py` loads, and
every project option is reported as unrecognised. Where the file must live
elsewhere, add `-c pytest.ini --rootdir .`.

**A judge returns a score, never an outcome.** The case passes, passes with a
warning or fails on what the harness concludes from the assertions and the
score against the threshold. Two judges disagree when their scores fall on
opposite sides of the threshold for one observation, and that observation is
examined before anything is filed.

### Filing a finding with the ticket tools

Two tools, run by hand from the repository root in this order. **None needs a
credential or spends anything**: each reads the committed recordings and
registers. Only step 1 in `--mode live` calls a provider, and it reads the keys
from the environment by variable name.

**1. Record the register.** Runs one engine's graded cases and folds the result
into `config/findings/<engine>.yaml`. A finding the run reproduces is recorded
as `open`; a finding whose case the run measured passing is removed, with the
line `REMOVED <case>, it passed on <date>`; a finding whose case skipped is kept
unchanged. A failure the run measures as passw is replaced by a fresh warning
entry (`consumer_ci.md` section 9.4.11).

```
python -m tools.findings --engine gemini --as-of 2026-11-06
python -m tools.findings --engine gemini --mode live --as-of 2026-11-06 --resolve-from-live
```

| Option | Does |
|---|---|
| `--engine` | The engine whose register is written. Required |
| `--as-of` | The date stamped on what changed, ISO, UTC. Required |
| `--mode` | `replay`, the default, or `live` |
| `--resolve-from-live` | Records a finding whose case passed as `resolved_upstream` instead of removing it. **Live only**: a replay replays our own recording and cannot show a model changed |
| `--dry-run` | Reports what would change and writes nothing |

**2. Write the tickets.**

```
python -m tools.ticket_report
python -m tools.ticket_report --engine gemini
```

| Writes, under `reports/tickets/` | Holds |
|---|---|
| `<engine>_findings.md` | Every filed finding of one engine on one page |
| `<engine>/<case number>_<behaviour>.md` | **One ticket per finding**, the file a person submits to the vendor |
| `FILING.md` | Every engine's findings grouped by cause. **Written only by a run without `--engine`**, its total covering every engine |

`--out-dir` writes elsewhere. `reports/` is gitignored, so tickets are
regenerated rather than committed, and an engine with no filed finding has its
old page and directory removed.

**Each ticket opens with a summary**: the prompt whole, each incorrect response
by the words that decided it, every response where the case failed, any
judgement at odds with its response's checks, and a flag where identical
responses were judged on opposite sides of the threshold, which the filing
sheet repeats (`consumer_ci.md` section 9.5.5.14).

**Each ticket carries** the problem, the request exactly as sent, every recorded
response with why it passed or failed, the judge prompt and score of each judged
response, the expected rule, and two reproductions: one outside this repository
and one through it. **A judgement is read from the judge the roster configures
first**, gemini today, and from any other judge's recordings, alphabetically,
only for an observation it left without one (`consumer_ci.md` section
9.5.5.8.2). A second judge's recordings come from a run naming it, such as
`--judge-mode live --judge-engine claude`.

There is no third step. A finding that our own repair removed, to the harness, a
rubric, a prompt or a system instruction, leaves no record once a run measures
its case passing, so nothing is held, withdrawn or written as a review ticket.

A register entry's `ticket` field is the one a person fills in, once the vendor
gives a reference; no tool overwrites it.

### Why they are not quarantined

A quarantine mechanism would mark a known finding as expected and turn the
gates green, so that a red meant something new. **It is deliberately not built
yet.** These findings are filed with each vendor once the project is complete,
and only those confirmed as model faults rather than harness or case defects; a
gate that reports them is the evidence, and quarantining them before they are
filed would hide the
result this project exists to produce. The mechanism is designed in
`consumer_ci.md` section 4.19.4 and its trigger is recorded there.

**The live ladders run monthly, one engine a day from the 1st, and skip a
month already measured.** The model version probe runs weekly and dispatches an
engine's ladder when its model changes, so the monthly run is a fallback for
inactivity. Every scheduled ladder waits for a reviewer before it spends; the
probe sends no prompt and does not wait.
`consumer_ci.md` section 4.18.3 holds the reasoning.

**A scheduled ladder measures the judge and the model, not our code.** Code is
certified when it changes: every commit here runs its gate, and every harness
commit runs this repository's suite. A ladder's replay jobs therefore usually
repeat a green gate; they stay as a free precondition for spending, catching a
dependency or runner change before the live rungs spend. Its live rungs
measure whether the judge or the model moved behind an unchanged name, which
is what a monthly run is for. `consumer_ci.md` section 7.3.1 lists what each
job certifies.

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
