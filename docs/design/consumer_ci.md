<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# Consumer CI Design

How this repository decides which harness it runs against, and what it refuses
to run against at all.

**Scope.** The harness owns the pipeline design; `AP-Harness-QC`
`docs/design/ci_pipeline.md` is normative for workflow naming, the credential
boundary, artifact contracts and exit code mapping, and none of it is restated
here. Section 3C of that document holds the branch topology this one
implements. What belongs here is the half that is **this repository's policy**:
which harness ref a case branch pairs with, and what happens when that ref has
not been verified.

---

## 1. The Problem A Pin Does Not Solve

`pyproject.toml` declares:

```
"ap-harness-qc @ git+https://github.com/apolskiy/AP-Harness-QC@main"
```

`pip` resolves that to whatever the branch head is at install time. It has no
notion of whether the commit it fetched passed anything. **A red harness main
therefore becomes the instrument silently**, and every finding produced with it
is attributed to the model under test.

That is the attribution inversion the entire design exists to prevent, arriving
through the dependency resolver rather than through a test.

Two separate defects hide in the single line above, and they need separate
answers:

| Defect | Answer |
|---|---|
| One pin cannot express a per-branch pairing | Section 2 |
| A pin says nothing about whether the commit is sound | Section 3 |

---

## 2. The Pairing: Which Harness A Case Branch Runs Against

A run is defined by a **pair** of refs. The topology is in `ci_pipeline.md`
section 3C; this section states how this repository resolves it.

### 2.1 The pin is data

`config/harness_pin.yaml` maps a branch of this repository to a harness ref.
The mapping is carried **on the branch**, which is the property that makes it
work: an expansion branch needing a harness extension declares its own pairing,
and merging it to `main` restores the `main` pairing because the mapping says so
rather than because somebody remembered to revert a line.

Editing the pin in `pyproject.toml` instead would make the edit part of the
change, and merging the change would merge the wrong pin with it.

**The `pyproject.toml` declaration stays and becomes a floor.** It is what a
clone installs when nothing resolves a pin, and `main` is the right default
precisely because `main` is the branch required to be green.

### 2.2 The branch naming convention carries the pairing

Two kinds of expansion branch exist and they pair differently, so the name has
to say which:

| Branch | Pairs with | Because |
|---|---|---|
| `main` | harness `main` | What its cases run against once merged |
| `stabilization` | harness `stabilization` | Stabilization on one side is verified against stabilization on the other |
| `expand-*` | harness `main` | New cases needing no new harness capability |
| `extend-*` | Its own entry, or harness `main` | New cases needing a harness extension, named when the branch is cut |
| Anything else | harness `main` | The default, and the safe one |

**`extend-*` is the branch the whole mechanism exists for.** A case that cannot
be written until the harness grows a capability has nowhere to run except
against the branch carrying that capability, and no constant pin can say so.

The distinction is a convention rather than an inference, because it is not
derivable: whether a case needs a harness extension is a fact about the case
that only its author knows, and guessing it from a diff would guess wrong in the
direction that fails silently.

### 2.3 First match wins, explicit before glob

Entries are ordered in the file and the first matching one is used. Literal
branch names are listed before patterns, so `main` cannot be captured by a glob
placed above it.

An unmatched branch takes the default rather than failing. Requiring an entry
per branch would make the mapping the thing that stops a branch being tested,
which is the same argument section 3C makes for the harness's own registry.

---

## 3. The Green Gate

### 3.1 Green is a property of a commit

"Is `main` green" has no answer, because `main` moves. The resolution is three
steps and the order is load-bearing:

1. Resolve the paired harness ref to a **commit**, with `git ls-remote`.
2. Ask about **that commit's** required workflow run.
3. Install **that commit**, by SHA, never by branch name.

Resolving, checking the branch, then installing the branch leaves a window in
which the commit installed is not the commit checked. The window is widest
exactly when the harness is busiest, and what it produces is a run whose record
names a verification that was performed on something else.

### 3.2 Absence of a result is not a pass

| Status of the required workflow on that commit | Green |
|---|---|
| Concluded `success` | **Yes** |
| Concluded `failure`, `timed_out` or `cancelled` | No |
| `in_progress` or `queued` | No |
| No run exists for that commit at all | **No** |

**The last row is the one that costs something to get right.** A commit with no
run is the normal state of a branch pushed seconds ago. Treating it as green
because nothing failed is how an unverified harness becomes the instrument, and
it is the same shape as a mistyped selector matching zero tests and exiting
clean.

**The latest attempt is what counts.** A workflow can be re-run, so the run with
the highest run number for that commit is authoritative and an earlier failed
attempt does not veto a later success.

### 3.3 `gate-on-change.yml` is the single required workflow

It runs on push, so every commit on every branch has one, which is what makes it
usable as a requirement. `regress-harness-on-branch.yml` is dispatch-only and
cannot be required of an arbitrary commit; when it has also passed that is
strictly more evidence and it substitutes for nothing.

Naming one workflow keeps "green" single-valued. A rule accepting any passing
workflow would be satisfied by a documentation lint.

### 3.4 Required on `main`, advisory elsewhere

A single strictness cannot serve both branches. Refusing on any non-green
harness ref would block case stabilization precisely while the harness is being
stabilized, which is when the pairing exists to be used. Refusing nowhere would
let a red harness produce results on `main`.

| Case branch | Paired harness ref not green | Outcome |
|---|---|---|
| `main` | **Refused.** Exit 4, the job fails | Nothing installed, nothing measured |
| `stabilization-*`, `expand-*`, `extend-*` | Proceeds, **ungated** | Runs, produces no verdict, records the code |

**An ungated run here is the same object a manual selection produces.**
`testing-standards.md` section 3.3 withholds a verdict when the selection was
not harness-computed. This withholds one when the **instrument** was not
established. Neither is a punishment, and both refuse to let a partial result
read as a full one.

**The strictness is per-entry data**, not a constant in a workflow, so raising
or lowering it is an edit to the mapping rather than to control flow. A branch
can be made strict without touching a conditional.

### 3.5 The code is `QC_HARNESS_UPSTREAM_UNVERIFIED`

Registered in the harness `test_taxonomy.md` section 6.2, because
`framework-rules.md` section 4.1 permits exactly one registry and it is not
here.

It is distinct from `QC_HARNESS_DEPENDENCY_UNMET`, which the fan-out uses for a
consumer that could not be reached. **Unmet means unavailable; unverified means
available but not established.** The operator response differs, so collapsing
them would cost the distinction that makes either actionable.

Both are `QC_HARNESS_*`, so neither is ever a finding about a model. Nothing was
measured.

### 3.6 The check cannot come from the thing it checks

`tools/harness_pin.py` **imports nothing from the harness**, and its only
third-party dependency is PyYAML, installed on its own line before the check
runs. That is a constraint rather than a preference, for two independent
reasons:

* It runs **before** the harness is installed, so a harness import is not
  available to it.
* A check fetched from the harness would be **asking an unverified ref to vouch
  for itself**, which is circular as an argument and not only as a dependency.

PyYAML breaks neither, because it is a general-purpose parser installed from an
index rather than anything this project or the harness controls. The line that
would matter is an import of `cmn`, and there is none.

It is also the right side of the boundary. The harness publishes a status; what
a consumer refuses to run against is the consumer's policy, and the harness's
**Downstream Reporting Only** directive means it neither enforces nor knows
about it.

### 3.7 The decision is pure, the fetch is thin

`assess_greenness` is a pure function of the API payload, the workflow filename
and the commit, on the same reasoning that makes the verdict a pure function of
observations: it is the part with rules in it, so it is the part that gets
tested. `git ls-remote` and one `urllib` call are the only I/O and carry no
policy.

An unauthenticated API call is rate limited to 60 an hour per address, which is
why the workflow passes `GITHUB_TOKEN`. **A rate-limited or failed query is not
green**, and falls into the same bucket as no run at all: nothing was
established. It is not an error that falls back to proceeding, because that
fallback would make the gate fail open under exactly the load that would hide it.

### 3.8 A ref that does not resolve refuses, and is a different code

Found 2026-09-23 by running the resolver against the real harness before its
`stabilization` branch existed. It raised, and the traceback exited **1**.

**Exit 1 is the one code this must never produce.** It means a suite measured
something and it failed, which CI reads as the model underperforming. A harness
branch that does not exist is the opposite of a finding about a model, and
letting an unhandled exception pick the exit code hands the attribution
inversion the whole design guards against to a stack trace.

| Situation | Can the run proceed | Exit |
|---|---|---|
| Ref resolves, gate green | Yes, gated | 0 |
| Ref resolves, not green, advisory branch | Yes, ungated | 0 |
| Ref resolves, not green, `require_green` | No | 4 |
| **Ref does not resolve** | **No, on any branch** | **4** |

**An unresolvable ref refuses regardless of strictness**, which is the one place
the advisory setting does not apply. Strictness governs whether an *unverified*
harness may be used; it cannot govern whether a *nonexistent* one may be,
because there is no commit to install. An advisory branch pointing at a missing
ref has nothing to fall back to.

**The code is `QC_HARNESS_DEPENDENCY_UNMET`, not
`QC_HARNESS_UPSTREAM_UNVERIFIED`.** This is the distinction section 3.5 draws
arriving in practice: unmet means unavailable, unverified means available but
not established. The operator response differs, and here it is specific: either
create the paired branch on the harness, or change this branch's entry.

The ordinary cause is benign. A case branch may declare a pairing with a harness
branch that has not been created yet, which is the expected state early in an
`extend-` branch's life.


### 3.9 A refusal stops the run, and development is deliberately exempt

Added 2026-09-24. Section 3.8 says what the resolver returns. This says what
the workflows must do with it, which was structural and unasserted.

**A regression run measures. A development run is how the thing being measured
gets built.** The two want opposite answers to the same red harness, and the
split is already in `config/harness_pin.yaml`.

| Branch | `require_green` | A red harness means |
|---|---|---|
| `main` | **true** | Exit 4. **Nothing installs and nothing runs** |
| `stabilization` | false | The run proceeds, ungated, yielding no verdict |
| `expand-*`, `extend-*`, `debug-*` | false | As above |
| Unmatched | false | As above |

**Refusing everywhere would block case stabilization precisely while the
harness is being stabilized**, which is when that pairing exists to be used.
Refusing nowhere would let a red harness produce results on main.

#### 3.9.1 The refusal has to actually stop something

Exit 4 fails the resolve step, which fails the resolve job, which skips every
job that needs it. **That is the whole mechanism, and it is a property of the
workflow rather than of the resolver.** A job carrying `if: always()`, or one
that simply never named the resolve job in its `needs`, runs anyway.

The failure mode is quiet and expensive: a full regression executes against a
harness whose own gate is red, and every finding it produces is attributed to
the model under test. It costs runner time on the free rungs and provider quota
on the live ones.

**Job-level and step-level conditions are different questions.** A step saying
`if: always()` inside a job that needs the resolver is correct and common: it
makes Gate 4 report even when Gate 2 failed, within a job that would not have
started at all had the resolver refused. Only a **job-level** status function
can outrun a refusal, so that is what `MQC_CAS_UNI_115706` checks.

#### 3.9.2 What the exemption protects, and what it does not

`debug-cases-on-demand.yml` is exempt by design, and `115707` holds it exempt:
refusing to debug against a harness that is not green would withhold the tool
exactly when it is needed. It tolerates a refusal rather than being spared one,
by letting the resolver fail without failing the step.

**The exemption is for the debug path, not for a live regression dispatched
from a development branch.** `evaluate-live-weekly.yml` spends provider quota
whatever branch it was dispatched from, so it waits for green regardless, and
`debug-cases-on-demand.yml` is the tool for spending deliberately against a
named subset while the harness is in flight. Two facts make that safe together:
the debug run records what it used, and it yields no verdict.

---


#### 3.9.3 A status function is permitted where it cannot outrun the refusal

Corrected 2026-10-01, from run 36920538819.

**The rule was "no job-level status function" and that is too blunt.** GitHub
implicitly conjoins `success()` onto any job condition carrying no status
function, and `success()` is false once **any** needed job has failed. So a band
gating on `needs.preconditions.result == 'success'` alone is skipped the moment
the band before it goes red, which is exactly the blocking section 3.12.1 exists
to prevent. The P2-P4 job was `skipped` with its matrix expression unexpanded,
because it never started at all.

**The property the rule protects is narrower than the rule.** What must hold is
that a refusal upstream stops this job. A status function alone does not
guarantee that; a status function **conjoined with a requirement that an
upstream job succeeded** does, because a refused resolver leaves that job
`skipped`, and `skipped` is not `success`.

| Condition | Runs when the resolver refused? | Runs when an earlier band failed? |
|---|---|---|
| none | No, by the implicit `success()` | **No.** The blocking |
| `needs.preconditions.result == 'success'` | No | **No.** Still the implicit `success()` |
| `always()` | **Yes.** The defect the rule was written for | Yes |
| `!cancelled() && needs.preconditions.result == 'success'` | No | Yes |

So the check now permits a status function **only** alongside an explicit
`needs.<job>.result == 'success'` for a job this one needs.

**The comparison has to be equality against success.** `result != 'failure'`
admits `skipped`, which is precisely the state a refused resolver produces, so a
condition written that way would outrun the refusal while looking careful.

**Two mechanisms again**, which is the pattern this project reaches for whenever
one would be a single point of failure: the status function decides that an
earlier failure does not block, and the success requirement decides that a
refusal does.

### 3.10 Gate 3 is not here, corrected 2026-09-26

`gate-on-change.yml` ran `pytest -m system` as Gate 3. **It collected nothing**,
because this repository defines no `SYS` case: every case here is either a `UNI`
precondition over the shipped corpus or a graded case in Gate 4. A marker matching
zero tests exits 5, so the step failed the job it was meant to complete on every
run, and the example in section 3.9.1 named it.

**Wiring is the harness's subject.** `SYS` covers dispatch, normalization and
pipeline wiring, none of which this repository owns, and the harness now carries
`MQC_CMN_SYS_122000` to `122002`, which run the whole chain to both a green and a
red verdict.

**What this repository proves is that its own corpus composes**, and that is Gate
4: every graded case, both sides replayed, against the harness the resolver
pinned. So the gate sequence here is 1, 2, 4, and the gap in the numbering is the
boundary rather than an omission.

| Gate | Runs | Why here |
|---|---|---|
| 1 | `pylint` | Governance parity, section 5 |
| 2 | `pytest -m unit` | The corpus preconditions |
| **3** | **Nothing. Withdrawn** | **No `SYS` case exists here to run** |
| 4 | `pytest -m "evaluator or tool or sec"` | The graded corpus, replayed |

### 3.11 A pending gate is waited for, not refused

Added 2026-09-28, after four consecutive paired pushes each produced a red
consumer run that carried no information.

The consumer gate fires on push. The harness gate runs lint, unit and system on
two platforms and takes minutes. So the resolver met an `in_progress` run every
time, refused, and a human re-ran the identical job to get the identical answer
once the upstream had finished.

**Section 3.2 is not weakened by this, and the distinction is the whole point.**
"Absence of a result is not a pass" refuses to read an unknown as a success.
Waiting is the opposite of assuming: nothing is concluded until the upstream gate
concludes it.

| What the resolver meets | What it does |
|---|---|
| A run still going | **Waits**, up to ten minutes |
| A run that concluded red | Refuses at once |
| A run that concluded green | Proceeds |
| **No run recorded yet** | **Waits**, on the same budget |
| A wait that runs out | Refuses. An unfinished gate established nothing |

#### 3.11.2 The wait is a tolerance, and the remedy for exceeding it is ordering

**Decided 2026-10-05 by the project owner**, after three gates refused on a
simultaneous push of both repositories:

```
QC_HARNESS_UPSTREAM_UNVERIFIED: gate-on-change.yml on ca05aa498bd5 is queued,
so nothing has been established yet. Waited 600s and it has not concluded,
so nothing is established
```

**The refusal was correct and the ten minutes were not the problem.** The owner's
position: pushing or merging the harness is a deliberate act, and if this
repository runs against the harness on `main`, that commit has to be green
before a run against it means anything. A run that cannot establish its
instrument is a non-starter, not a scheduling inconvenience.

| | |
|---|---|
| The operating rule | **Push the harness, wait for its gate, then push here** |
| What the wait is for | Absorbing the seconds-to-minutes lag of a near-simultaneous push, per section 3.11.1 |
| What the wait is not | A substitute for the harness having passed |

**So the budget is deliberately not configurable, and that is worth stating
because the alternative was available.** `WaitPolicy.timeout_sec` is a default
with no CLI flag and no workflow input, which in this project is normally a
defect: a value that exists and cannot be reached. Here it is the intended
shape. A longer budget buys nothing a correctly ordered push does not already
have, and it costs the thing the refusal protects:

**A wait long enough to cover any harness gate is a wait long enough to hide
that the harness gate failed.** The run would sit for twenty minutes and then
refuse for the real reason, having spent the time to learn what the ordering
would have told it immediately. **Waiting is not free when what it waits for
might be red.**

**This does not relax section 3.9.** A refusal still stops the run, development
branches are still exempt with `require_green: false`, and the exemption is
still what lets stabilization work proceed against a harness in flight. The
rule here is about `main`, where `require_green: true` already says the harness
must have passed.

#### 3.11.1 A run not yet registered is pending, not absent

Corrected 2026-09-29, on the first paired push after section 3.11 was written.

**The row above used to say absence was refused at once**, on the reasoning that
no amount of waiting grows a run. That was wrong, and in the narrowest possible
way. The harness was pushed at 02:25:15 and this repository at 02:25:22; the
resolver asked GitHub about the harness commit before GitHub had registered a
run against it, and refused a commit whose gate started moments later and passed
every job.

**Nothing in the API distinguishes the two.** A commit pushed one second ago with
no run yet and a commit that will never have a run return the same empty list.
The only thing that separates them is how long you look, so the resolver looks
again on the same budget it already waits on.

**Section 3.2 still holds, and this is the reason the wait is bounded.** Waiting
postpones concluding that there is no run; it never reads absence as a pass. A
commit that genuinely has none is refused when the budget runs out, with the same
`QC_HARNESS_UPSTREAM_UNVERIFIED` it always carried.

The cost of the old behaviour was a red consumer run on every paired push — the
same toil section 3.11 was written to remove, arriving seven seconds earlier in
the window than the case that found it.

**Ten minutes, and the bound matters.** The harness gate finishes in two to three,
so the budget absorbs a queued runner without letting a wedged upstream run hold a
consumer job all day.

**The clock is injected**, so `MQC_CAS_UNI_115318` exercises the timeout without
spending it.

### 3.12 One job per band, because the job name is the diagnosis

Added 2026-10-01.

**`preconditions` ran Gate 2 and Gate 4 in one job**, so a red there meant
either "our harness or corpus is broken and nothing was measured" or "the model
underperformed". Those are the two categories `framework-rules.md` section 3.1
exists to separate, and the ones `cmn_verdict_and_cli.md` section 7.3 keeps apart
as exit 3 against exit 1. One job name collapsed them, and reading a red meant
finding the failing case, opening the test plan and looking up its priority
before knowing which kind of problem it was.

**A failing band has a different remedy at each level**, which is why the band
belongs in the job name rather than in an artifact:

| Job | A red means | What follows |
|---|---|---|
| `lint` | Our code | Fix it |
| `preconditions, our defect` | **Our harness or corpus.** Nothing was measured | Fix it, blocking |
| `graded P0, release blocking` | A model defect at P0 | Open it, fix before release |
| `graded P1, release blocking` | A model defect at P1 | Open it, fix before release |
| `graded P2-P4, pass floor` | The band fell below the floor | Open it, quarantine the case, review sets the date |

**Gate 2 leaves the graded job entirely.** The band jobs take it on `needs:`, so
"a precondition failure means the graded layers never execute" is expressed by
the job graph rather than by step order inside one job.

#### 3.12.1 The bands are chained, and a failure does not hide the next

Each band `needs:` the one before it, which orders them and lets the carried
outcome record travel. **They run on `success()` of the preconditions job and
otherwise on `!cancelled()`**, so a P0 failure still lets P1 and P2-P4 report:
the point of the split is to see every band's state at once, and a chain that
stopped at the first red would be the single job again with extra steps.

**The carry record travels as an artifact**, uploaded under a name carrying the
band and the platform. The harness refuses a record whose provenance moved
(`cmn_verdict_and_cli.md` section 7.6.1), so the two mechanisms that keep one
platform's outcomes out of another's run are the artifact name and the
`platform` field, which is the same two-independent-mechanisms pattern the
debug-artifact exclusion uses.

**`MQC_CODE_REF` and `MQC_CASE_REF` are set per job** from the resolved harness
commit and this repository's commit, because a commit is a property of the
checkout and the provenance guard compares both.

#### 3.12.2 Only the lower band answers to a floor

P0 and P1 gate on pytest's exit status, and that is exactly V1: "any P0 or P1
observation not passing fails the run" and "this band had a failure" are the
same statement, so no verdict computation is needed to enforce it.

**P2-P4 is the only band where a failure is not automatically fatal**, so it is
the only one needing a pass rate. `tools/band_floor.py` reads the band's JUnit
and compares against `VerdictConfig.pass_floor`, which it imports rather than
restates: a floor written twice is a floor that will eventually disagree with
itself.

**A harness error is still fatal there.** The tool refuses when the report is
missing or unparseable, and when any case reports an `error` rather than a
failure, because an error is our defect and the floor is about the model. That
distinction is the whole reason the band has a floor at all.

---

## 4. Test Inventory: `MQC_CAS_UNI_`

Identifiers come from the `CAS` block, 10401-10499, partitioned in the harness
`test_taxonomy.md` section 3.2.1.

| ID | Category | Behaviour |
|---|---|---|
| `115300` | P | `a_named_case_branch_resolves_to_its_declared_harness_ref` |
| `115301` | P | `a_glob_entry_matches_an_expansion_branch` |
| `115302` | B | `an_unmatched_branch_takes_the_default_pairing` |
| `115303` | B | `an_explicit_entry_wins_over_a_glob_listed_after_it` |
| `115304` | P | `a_successful_required_run_on_the_commit_is_green` |
| `115305` | N | `a_failed_required_run_is_not_green` |
| `115306` | N | `no_run_at_all_for_the_commit_is_not_green` |
| `115307` | N | `a_run_still_in_progress_is_not_green` |
| `115308` | N | `a_success_on_a_different_commit_does_not_make_this_one_green` |
| `115309` | N | `a_success_from_an_unrequired_workflow_is_not_green` |
| `115310` | B | `the_latest_attempt_decides_when_a_run_was_retried` |
| `115311` | P | `main_requires_green_and_a_stabilization_branch_does_not` |
| `115312` | N | `the_module_imports_nothing_from_the_harness` |
| `115500` | N | `every_callable_carries_parameter_and_return_hints` |
| `115501` | N | `pep_563_future_annotations_import_is_rejected` |
| `115502` | N | `every_python_file_carries_its_mit_spdx_header` |
| `115313` | N | `an_unresolvable_paired_ref_refuses_rather_than_crashing` |
| `115706` | N | `a_test_executing_job_that_outruns_a_refusal_is_reported` |
| `115707` | N | `a_debug_workflow_blocked_by_a_red_harness_is_reported` |
| `115504` | N | `a_runbook_command_naming_an_undeclared_input_is_reported` |
| `115314` | N | `a_case_referent_naming_no_inventoried_case_is_reported` |
| `115315` | N | `a_pairing_not_covering_a_dated_branch_is_reported` |
| `115316` | N | `a_pull_request_taking_its_source_strictness_is_reported` |
| `115505` | N | `a_file_open_declaring_no_encoding_is_reported` |
| `115506` | N | `an_identifier_outside_its_module_block_is_reported` |
| `115709` | N | `a_graded_job_not_naming_its_engine_is_reported` |
| `115009` | P | `the_obfuscated_payloads_survive_a_load_as_code_points` |
| `115010` | N | `a_graded_evaluation_rule_without_a_rubric_is_reported` |
| `115600` | N | `a_requirement_traced_but_stated_in_no_plan_is_reported` |
| `115601` | N | `a_matrix_row_naming_a_test_the_suite_lacks_is_reported` |
| `115317` | N | `a_readme_figure_disagreeing_with_the_repository_is_reported` |
| `115318` | B | `a_pending_harness_gate_is_waited_for_not_refused` |
| `115200` | N | `harness_files_are_not_located_by_directory_adjacency` |
| `115201` | N | `the_roster_resolves_and_names_engines` |
| `115011` | N | `a_graded_case_naming_an_unbuilt_pair_is_reported` |
| `115202` | N | `fill_gaps_reaches_the_plan_the_channel_uses` |
| `115203` | B | `a_lower_band_is_judged_against_the_floor` |
| `115204` | P | `a_skip_leaves_the_denominator` |
| `115205` | N | `an_error_refuses_rather_than_averaging` |
| `115206` | N | `the_candidate_engine_reaches_the_plan_the_channel_uses` |
| `115602` | N | `a_collected_test_named_in_no_matrix_row_is_reported` |
| `115708` | N | `a_workflow_emitting_one_mandated_artifact_is_reported` |
| `115408` | P | `the_tool_writes_what_reconciling_decided` |
| `115409` | P | `one_dispatch_session_serves_a_whole_run` |
| `115410` | P | `the_session_records_the_models_it_served` |
| `115411` | N | `the_tool_refuses_a_date_it_cannot_parse` |
| `115406` | P | `the_named_judge_engine_is_the_one_that_grades` |
| `115407` | P | `the_named_observation_count_is_the_one_dispatched` |

**Inventory: 50 cases, 34 negative, 11 positive, 5 boundary.** Counted from the rows on 2026-10-03, when the stated figure was wrong on three of its four numbers: nothing checks this one, only the README equivalent.

### 4A. The harness is a dependency, not the directory next door

Added 2026-09-28, from the first CI run in which a judged case was replayable.

**Gate 4 failed in CI and could not fail on any developer's disk.**
`graded_support` located the engine roster and the price table at
`../AP-Harness-QC/config/`, which is true only where both repositories are
checked out side by side. CI installs the pinned harness from git, so the path
did not exist, an absent file loaded as an empty mapping the way an optional
one does, and the run failed with `judge engine 'gemini' is not on the roster`
— a misconfigured instrument, reported three layers from its cause.

**The local suite could not catch it**, because the sibling is always there.
Gate 4 had also never reached this code before: until the `amb` family was
recorded, every graded case skipped on a missing fixture before a judge was
ever built. The first replayable judged case is what exposed it.

**So the harness ships its own configuration** and is asked where it landed,
through `cmn.config.packaged_roster_path` (harness `cmn_verdict_and_cli.md`
section 10.37). Nothing here reaches out of this repository to find harness
files.

`MQC_CAS_UNI_115200` asserts the shape rather than the outcome, over the syntax
tree rather than the text: no path expression in `tests/` or `tools/` may name
the harness directory. Scanning the text flagged the prose that explains the
rule and the pin's own `apolskiy/AP-Harness-QC`, neither of which reaches
anywhere. `MQC_CAS_UNI_115201` pins the consequence — the roster resolves and
names engines — because an empty roster is what the failure actually looked
like.

### 4.1 Why the negatives outnumber the positives

Every row in the table at section 3.2 is a way for the gate to **fail open**,
and a gate that fails open is indistinguishable from no gate at all until the
day it matters. `115306` through `115309` are each one such way, written
separately because a single case asserting "not green" would pass with an
implementation that returned `False` unconditionally.

`115312` is the boundary check for section 3.6, and it is a source check rather
than a behavioural one because the defect it guards is an import that works
perfectly on a developer machine where the harness is already installed, and
fails only in CI at the one moment the gate is supposed to run.



### 4.2 The refusal is only worth what the workflows do with it

Added 2026-09-24. `115706` and `115707` are the two halves of section 3.9, and
they are separate identifiers because they are opposite claims: one says a
regression run stops, the other says a debug run does not.

**Both are source checks on workflow definitions**, which is the only place
the property lives. `115313` establishes that the resolver refuses; nothing
established that a refusal reached anything, so the protection was structural
and unasserted, which is the state this project has learned to distrust.
### 4.3 The branch policy reaches the pairing

Added 2026-09-24. `115314` and `115315` cover what `ci_pipeline.md` section 3C.6
means on this side, where branches are dated and the pairing mapping has to
match them.

**`115314` is the half that cannot live in the harness.** A referent naming a
case identifier is checked for existence, and the inventory it is checked
against is this repository's. The harness checks its own identifiers against
its own, which is one rule enforced by one implementation over two inventories,
not two rules.

**`115315` reports a pairing that no longer covers the branches CI runs on.** A
dated branch matching no entry takes the default, which is silent and pairs it
with `main`, so a stabilization branch could quietly run against the wrong
harness while looking configured.

---

### 4.12 Both mandated artifacts, checked on this side too

Added 2026-10-02, from a harness finding that reached this repository.

`testing-standards.md` section 5 mandates **both** JUnit XML and Allure raw
results, and they answer different questions: JUnit is how a failure is
triaged, Allure is what a report is assembled from and what readiness is judged
against. Emitting one is not a reduced record, it is a missing reader.

**`debug-cases-on-demand.yml` emitted JUnit alone.** It passed `--out-dir` and
`--junitxml` with no `--alluredir`, so the one workflow reached for when
something has already gone wrong produced no report. **It is already fixed
without this workflow changing**, because `--out-dir` now derives both
destinations: harness `cmn_verdict_and_cli.md` section 7.1.0.2.

| Workflow | Emits both |
|---|---|
| `gate-on-change.yml`, every band | Yes, throughout |
| `evaluate-live-weekly.yml`, every leg | Yes, throughout |
| `debug-cases-on-demand.yml` | **Now, through `--out-dir`** |

**The scanner lives in the harness and is called from both sides.** The harness
owns no case data and this repository owns its own workflows, so
`cmn.code_standards.artifact_mandate_gaps` takes a root and
`MQC_CMN_UNI_112525` and `MQC_CAS_UNI_115708` call it with one each. The same
one-implementation-two-callers arrangement as the encoding and header rules,
for the same boundary reason.

**This check was green when it was written, and that is recorded rather than
hidden.** The flag implementation fixed the gap before the case existed, so the
case was verified by injection instead: removing `--out-dir` from the debug
workflow makes it report that workflow, which is the state this repository was
in until 2026-10-02.

### 4.13 The judge engine a run names, and the one that graded it

Added 2026-10-02, from reading the last two dated flag gaps.

**`judge_binding` passed a literal empty string where the judge engine goes.**

```
channel = _channel(
    "",                 <- the judge engine, hardcoded
    plan.mode, plan.record, ...
)
```

So `--judge-engine openai` resolved to gemini, which the probe that found this
confirms directly:

| Passed | Graded by |
|---|---|
| nothing | gemini |
| `--judge-engine openai` | **gemini** |
| `--judge-engine claude` | **gemini** |

**The harness side was never wrong.** `judge_channel_from_roster` takes the
override and resolves `engine or load_judge_engine(...)`, which is the
documented precedence; it was reached with an empty first term. Harness
`tier3_evaluation.md` section 5A.3 carries that half.

**The flag is recorded, which is what makes it a defect rather than a missing
feature.** A run naming a judge produced metadata naming it while a different
engine graded, so the artifact attributed scores to an instrument that did not
produce them. For a repository whose headline finding is self-preference, a
comparison of candidate against judge, that is not a degraded measurement but a
differently-meaning one.

**Latent, and treated the same.** No workflow passes the flag and no case did,
which is why nothing shipped is affected and also why it survived: the declared
gap in `flag_coverage.yaml` said "nothing covers the flag reaching it", which
was accurate and read as a coverage gap rather than as the defect it was
describing.

**The empty string is why it read as correct.** `_channel("")` and
`judge_channel_from_roster(..., engine or None)` both treat empty as "take the
configured one", so the call site looked like a deliberate choice to use the
configured judge rather than like a dropped argument. `115406` fails on the
behaviour instead of on the shape.

### 4.13.1 The observation count, covered rather than fixed

`--observations` is read: `observation_count` takes it as an override above the
roster entry. Nothing varied it and asserted the dispatched population changed,
which the same gap entry recorded accurately.

**It interacts with escalation, and that is what `115407` pins.** A run naming
three observations where one disagrees still earns two more, because the
override sets the count the run begins with and
`cmn.observations.further_observations` decides what a disagreement adds. An
override that suppressed escalation would make a named count quietly mean
something different from a configured one.

### 4.14 Confirming a quarantine entry, which is the only thing that can

Added 2026-10-02. Harness `cmn_verdict_and_cli.md` sections 4.6.5 and 4.6.10
specify the split: the harness decides, this repository runs and writes.

**The entries live here**, at `config/quarantine/<engine>.yaml`. A quarantine
entry can only be about a graded case, and the harness holds none, so the data
is this repository's and the harness ships none of it.

`tools/quarantine.py` re-observes every case its engine's file names, asks
`cmn.quarantine.reconcile` what each entry becomes, and writes the file back.

| Observed | Action |
|---|---|
| Every observation passed | The entry is dropped |
| Any observation failed | `quarantined_on` and `observed_model` are stamped with today's run |
| Nothing observed | The entry is kept and reported as undecided |

**An entry can outlive its case.** A renamed or deleted case leaves an entry
naming a pair the corpus no longer defines, and that entry is **unobservable
rather than passing**: dropping it would be deciding on no evidence, and raising
would let one stale entry block every other entry in the file. It reports and
falls through to undecided, which is the same outcome as a case nobody ran,
because it is the same situation.

**It re-observes under the escalation policy, not once.** Three observations,
with two more on a single disagreement, per harness section 4.9.2. Dropping an
entry on one green observation would un-quarantine a flaky case on its lucky
run, which is exactly the reading the repeats exist to prevent.

**It spends money, and that is the point.** "Does this still fail?" is a
question about the current model, so the useful run is live. It therefore takes
`--mode` and `--max-spend` like any spending surface, and a replay confirms
only that the recorded fixtures still fail, which is a different question worth
asking separately.

**It writes by default and `--dry-run` previews.** Writing is the job; the
review happens on the diff, like any other configuration change. The tool
prints every action whichever mode it is in, so the change is legible before
the file is read.

**It never commits.** The operator reviews the diff and commits, which is the
project's standing rule and also the reason this is a tool rather than a step
in a gate: a gate that rewrote tracked configuration would race between the
platform and band legs that run in parallel.

#### 4.14.1 A dependent of a failed base is deferred, not unknown, and the set is static

**Decided 2026-10-05 by the project owner**, while reviewing what claude's nine
skips mean for a vendor report.

**A downstream skip is not a pass and it is not an unknown either.** It is
deferred measurement: the case did not run because its foundation did not hold,
and when that finding is fixed the case runs. So the right reading of a skip is
"pending an upstream fix", which is a statement about a known cause rather than
an absence of information.

**And the case will then be measured on a working foundation, which is the
point of the cascade.** A dependent only ever executes where its base holds, so
its pass means what it says. Running it against a broken foundation would
produce a result about nothing: the observation this subsection exists to
record is that the skip is protecting the dependent's result, not withholding
it.

| Reading | Correct? |
|---|---|
| A pass | **No.** Nothing was measured |
| An environmental failure | **No**, which is why `skip_counts_toward_rate` already excludes it from the skip rate |
| An unknown | **No.** The cause is a named, catalogued finding |
| **Deferred behind a named finding** | **Yes** |

### The quarantine inherits downwards

**When a base is quarantined, its dependents are deferred with it**, carrying
the same reason and the same expiry. A bare skip beside a quarantined base
states the consequence without the cause, and a reader then has to reconstruct
the graph to learn why a case did not run.

**This is specified now and built with the quarantine**, whose trigger is
publication per section 4.19.4. Writing the rule down first is the point: the
decision is cheap today and expensive once the mechanism exists and treats
dependents as an afterthought.

### The deferred set is computable before the run, not only at skip time

**"On skip or earlier" resolves to earlier**, because the graph is static. A
case declares its foundation with `@pytest.mark.depends_on("154100")`, so the
transitive set blocked by any finding is a closure over declarations plus the
findings register, with no execution at all.

Computed that way on 2026-10-05, against the registers:

| Engine | Finding | Cases deferred behind it |
|---|---|---|
| claude | `154100` | **4** — `154104`, `154105`, `154106`, `154108` |
| claude | `154103` | **3** — `154200`, `154201`, `154202` |
| claude | `134109` | 1 — `134110` |
| claude | `134205` | 1 — `134204` |
| gemini / openai / grok | `134205` | 1 each — `134204` |

**Totals: claude 9, gemini 1, openai 1, grok 1 — which match the skips the runs
actually produced, exactly.** The static closure and the runtime cascade agree,
which is what makes the earlier computation trustworthy rather than merely
cheaper.

**So a vendor report can state the cost of one defect.** "Fixing `154100`
unblocks four cases" is a different and better sentence than "four cases
skipped", and it is available before anything is run.

### 4.15 The session did not survive the run, and the ceiling stopped nothing

Found 2026-10-02 while implementing `tools/quarantine.py`, which passes a spend
ceiling and would have been governed by none.

**`dispatch_session` built a fresh session on every observation.** It carries
no cache, and `observe` calls it per dispatch, so every piece of run-level
state it holds was discarded between observations:

| State | Intended | Actual before this |
|---|---|---|
| `spent` against `max_spend` | Accumulates until the ceiling refuses | **Reset to 0.0 each observation**, so the ceiling could never be reached |
| `last_request_at` | Spaces requests at the roster's `spacing_sec` | Reset, so the free-tier spacing was never applied between observations |
| `consecutive_failures` | Opens the circuit breaker | Reset, so the breaker could not open |

**`_channel`'s own docstring asserts the opposite.** It explains its cache by
saying it is "the same reason `DispatchSession` outlives one dispatch", and the
session did not outlive one dispatch. A document claiming a property the code
lacks is worse than silence, because a reader stops looking: that is the rule
`testing-standards.md` states about design, found here in a docstring.

**This is the first instance of the recurring shape, reopened.** Harness
`cmn_verdict_and_cli.md` section 7.1.0.1 records `--max-spend` as the original
case of a flag that reached nothing, and `MQC_CAS_UNI_115208` closed it by
asserting the flag reaches the session's ceiling. **It does, and that was half
of a two-part claim**: a ceiling on a session rebuilt per observation is still
a ceiling that stops nothing. `115208` is correct and was never sufficient.

| Established by `115208` | Not established by anything |
|---|---|
| `--max-spend` reaches `DispatchSession.max_spend` | That the session holding it survives more than one dispatch |

**Cached on what defines a session**, the engine and the ceiling, in the same
shape `_channel` already uses. Keying on the configuration object would cache
on identity and tie the lifetime to pytest's internals rather than to the two
values that actually determine the session.

### 4.15.1 The session now says which models it served

`reconcile` stamps the model a re-observation ran against, and nothing could
report it: the resolved model reaches `DispatchSession.record_spend` and was
used for pricing and then dropped, while `EvaluationResult` never carried it.

**The session records it, because the session is already the run's state.** It
keeps `unpriced` for exactly this kind of question, so `served` sits beside it
and answers "what did this run actually run against" for any caller.

**One model or none.** A caller reading `served` and finding two is looking at a
mixed corpus, which is the same condition `mixed_model_engines` reports from
observations, and `reconcile` treats an empty model as the window alone
applying rather than guessing between them.

### 4.16 A live run on both sides is required before the work is called complete

Recorded 2026-10-02 at the project owner's instruction.

The ladder's third rung, `live, live`, is **mandatory before this project is
presented as finished**, for two things a replay cannot give:

| | |
|---|---|
| **Cost** | What a full evaluation of one engine actually costs, measured rather than scoped. The scoping arithmetic exists and has been within a factor of three of the outcome; an estimate is not a figure |
| **Real findings** | A replay reports what the recorded models did. A finding filed with a provider has to be about the model they are serving now |

**It runs last, and the order is not a preference.** A live run that produced
artifacts which cannot say which engine answered would spend money to buy an
unattributable record, which is the state the artifacts were in until the
emission hook of harness `cmn_verdict_and_cli.md` section 5. So the order is:
the emission hook, then per-engine jobs, then the live run.

| Precondition | Why it has to come first |
|---|---|
| The emission hook | Otherwise a finding cannot be attributed to an engine from the artifact, and the run has to be watched rather than read |
| The reproduction attachment, section 5.3 | A ticket is filed from the artifact; without it the call has to be reconstructed by hand, per finding |
| **A spend ceiling that accumulates** | `--max-spend` reset every observation until section 4.15, so a live run had no working budget guard at all |
| Per-engine jobs | A finding is filed with one provider, so the run that produced it has to be one engine's run |

**Each engine is run and reported separately**, because each finding is filed
separately with the provider that owns it. That is the reason the jobs separate
rather than a preference about CI layout.

### 4.17 One job per evaluated engine, because a red has to say which engine

Added 2026-10-03 at the project owner's instruction: a job covering several
engines produces a result nobody can act on, and an engineer or an analysis has
to go digging through a log to find out which model failed.

**Both workflows evaluated one engine of three.** Every graded step named
`--engine gemini` literally, so `openai` and `claude` were measured only by
hand. The findings this project reports about them came from local runs rather
than from any gate.

**This is section 3.12's argument about bands, applied to engines.** That
section put each priority band in its own job and gave the reason: "The band in
the job name answers that before anything is opened." A graded failure is a
finding about **one model**, so the engine belongs in the job name for exactly
the same reason, and more strongly:

| | |
|---|---|
| A red naming no engine | Someone opens the log and searches to learn which model failed, per failure |
| **Each finding is filed with one provider** | The run that produced it has to be one engine's run, or the ticket cites a run that measured three models |
| A model regresses while another improves | One job's status cannot express both, so the signal is whichever happened to fail |

**In the gate it costs nothing.** The graded bands run in replay, and fixtures
exist for all three engines: 204 recorded responses for `gemini`, 210 for
`openai`, 192 for `claude`. No credential, no quota, pure CPU.

**Each engine is a separate job and not a matrix leg**, for the reasons section
4.17.3 gives: a matrix aggregates its legs into one status, so one engine's
finding would redden a check covering three.

#### 4.17.3 Separate jobs, not matrix legs, and the sequence is `needs:`

Revised 2026-10-03, after the matrix landed, and **superseded the same day by
section 4.19**: separate jobs were not enough either, because a workflow run
has its own conclusion. The reasoning below is why a matrix was wrong and still
holds; the shape it chose was one step short.

**A matrix is one job with legs**, and the job is the unit everything else
reads:

| | Matrix legs | A job per engine |
|---|---|---|
| One engine fails | **The job is red**, so a required check on it is red for a finding about a model we do not own | That engine is red and the others report their own verdict |
| Re-running one engine | Re-running a leg, which is not a thing a reader can point at | Re-running a job |
| Diagnosis and quarantine | Three engines' findings arrive under one job | Per engine by construction, which is how the quarantine files are already keyed |
| Adding an engine | A matrix value | One call |

**The bands are not triplicated to get this.** The graded bands move into
`graded-engine.yml`, a workflow taking the engine as an input, and the gate
calls it once per engine. Adding an engine is one call, which is B8's "an entry,
never a module" applied to CI rather than to the roster.

**The sequence is `needs:`, and deliberately not a shared concurrency group.**
A concurrency group is a mutex holding exactly one pending job, so three engines
contending for one slot means one is cancelled, and `testing-standards.md`
section 2 records what that costs: "the losers surface as cancelled, which reads
as failure". Serialising by cancellation would manufacture the red this
separation exists to remove.

**Each link runs whatever the engine before it concluded.** `needs:` alone skips
a job whose dependency failed, which would re-couple exactly what the
separation decoupled: a red on `gemini` would mean `openai` was never measured.
So each call carries `if: ${{ !cancelled() && needs.preconditions.result ==
'success' }}`, which keeps the order, keeps the precondition gate, and drops the
coupling between engines.

**What the order buys, beyond politeness to a provider.** A sequence is
reproducible: the same engine meets the same quota state on every run, so a
rate-limited leg is a finding about pacing rather than about which three jobs
happened to start together. The replay gate needs none of this and gets it
anyway, because the ordering is a property of the call graph rather than of the
mode.

**The weekly ladder is a workflow per engine**, staggered across the day, which
section 4.18 specifies. The gap recorded here on 2026-10-03 proposed per-engine
jobs inside one weekly workflow and was superseded the same day: a job per
engine still leaves one run, one status and one history covering three vendors.

#### 4.17.1 The carried outcomes must be keyed by engine, or three engines overwrite one

The bands chain: P0 uploads `reports/carry.json` and P1 takes it, so a
foundation established once is not re-established. The artifact is named
`carry-after-p0-<os>`.

**Three engines on that name is one name.** Each engine's P0 would upload to it
and P1 would download whichever finished last, so two of the three bands would
proceed on another engine's outcomes and report about a model they did not
measure.

**That is the defect the judgement fixtures already had.** `JudgementKey` lacked
the candidate engine, and recording `openai` overwrote 96 `gemini` judgements
that were only recovered because a hash guard refused them. The shape is
identical: an artifact key missing the dimension that distinguishes two runs.
So the engine joins both the carry name and the report name, by design rather
than after an overwrite.

#### 4.17.2 A live leg with no credential skips, and never fails

The weekly ladder runs live, so each engine's leg needs that engine's key.
A leg whose secret is absent **skips**: an absent credential is our
configuration, not a finding about a model, and `framework-rules.md` section 4
resolves a `QC_HARNESS_*` condition to skip or broken and never to a failure.

**Failing it would attribute our misconfiguration to the provider**, which is
the error the consumer-regression gate exists to avoid and the same reason an
undated quarantine entry does not fail a run (section 4.6.4 of the harness
design).

**The legs stay serialised.** `max-parallel: 1` within the run and a
concurrency group keyed on engine and mode between runs, which
`testing-standards.md` section 2 already specifies: priority bands share a
provider quota, and so do a provider's own legs.

### 4.18 One weekly workflow per engine, staggered, because nothing aggregates

Added 2026-10-03 at the project owner's instruction, superseding the dated gap
section 4.17 recorded a few hours earlier. That gap proposed per-engine **jobs**
inside one weekly workflow; the instruction is stronger and better founded:
**separate engines, separate evaluations.**

**There is nothing to aggregate.** These are the products of different
companies, evaluated against one harness and one corpus. A combined weekly
result is an average over three vendors, which answers no question anybody
asks: nobody ships against it, nobody files it, and nobody can read a regression
out of it.

| What a reader wants | What an aggregate gives |
|---|---|
| Did **this** model regress since **its** last evaluation | A figure that moved because a different vendor's model moved |
| A history per engine, to compare engine against engine | One history whose points mix three subjects |
| A re-run after **one** vendor ships an update | A re-run of all three, spending on two that did not change |

**Engine against engine is a comparison of separate evaluations**, not a
property of one run. The artifact contract already carries what a comparison
needs, per engine; aggregating first destroys exactly the dimension the
comparison is over.

#### 4.18.1 Separate workflows, not separate jobs

A job per engine inside one workflow still leaves one workflow run, one status,
one history and one artifact set to pick apart.

| | One workflow, jobs per engine | A workflow per engine |
|---|---|---|
| Status | One run's conclusion covers three vendors | One per engine |
| History | One run history, points mixing subjects | One per engine, which is what a trend needs |
| A model update | Re-runs three engines | Re-runs the one that changed |
| Schedule | One time for all three | **Its own time**, which is what makes the stagger possible |

The ladder itself is unchanged and moves into `evaluate-engine.yml`, taking the
engine as an input. Each engine gets a thin caller carrying its own schedule.
Adding an engine is a caller, which is the same shape `graded-engine.yml` has in
the gate.

#### 4.18.2 The stagger is the serialisation, and that removes a mechanism

Eight hours apart in roster order, **reserved and not yet active** per
section 4.18.3:

| Engine | Fires |
|---|---|
| `gemini` | Monday 02:00 UTC |
| `openai` | Monday 10:00 UTC |
| `claude` | Monday 18:00 UTC |
| `grok` | **Tuesday** 02:00 UTC |

**The fourth engine rolls the day over rather than narrowing the gap, and that
choice is the whole argument below.** Eight hours into one day holds three
engines, so a fourth could either take a 6-hour spacing across Monday or
continue the sequence onto Tuesday. Narrowing it would trade the property this
section exists to establish — that the gap is far longer than a ladder takes,
so an overrun is a finding rather than a collision — for a tidier table.
**The day is the cheap thing to spend; the invariant is not.**

**Serialisation becomes a property of the clock rather than of a lock.** With
the three never overlapping by schedule, there is no cross-engine concurrency
group, no `needs:` chain between engines, and therefore no cancellation and no
coupling. `testing-standards.md` section 2 warns that a concurrency group holds
one pending job and cancels the rest; the stagger needs no group at all.

**Each engine still guards against overlapping itself.** A concurrency group
keyed on the engine prevents a second run of the same engine starting while one
is live, which is precisely the use that section endorses: "correct only for
preventing overlap *between* runs."

**And a run that overruns its window is visible rather than contended.** Eight
hours is far longer than a ladder takes, so a leg still running when the next
engine fires is a finding about pacing or about a provider, not a scheduling
accident.

#### 4.18.3 The schedule stays withheld, and two things gate its return

Each engine's workflow carries `workflow_dispatch` alone. The slot is reserved
and documented in the file, and the cron is not written yet.

**A live firing spends real money**, so a schedule is worth having only once
something is reading its output. Two conditions gate it, and neither is a
matter of taste.

**One: the findings already known have to be triaged.** The gate's replay
reports **24 findings across four engines** — 2 for `gemini`, 8 for `openai`,
10 for `claude` and 4 for `grok`, the last added when that engine was recorded
on 2026-10-04. A weekly live run would report at least those, so every firing
would be red for reasons recorded days earlier. **A cron that is always red communicates nothing**, and
the remedy is the quarantine mechanism of 2026-10-02 rather than a threshold:
each finding is accepted into its engine's quarantine with a reason and a
ticket, or it is a defect in our corpus.

**Two: the weekly must decline when anything else has already evaluated this
engine.** The weekly is a **fallback for inactivity**, not a model-update
tracker. Any evaluation of that engine inside the window makes it redundant,
whatever prompted the earlier one:

| What already ran this cycle | The weekly |
|---|---|
| An evaluation after that vendor shipped a model | **Skip** |
| An evaluation after the harness was updated | **Skip** |
| An evaluation after the corpus or a test changed | **Skip** |
| Nothing | Run. This is the only case the cron exists for |

**Stating it as "were there any runs in between" rather than "did the model
change" is what makes it cheap.** The run does not have to know why an earlier
evaluation happened, or which model version it measured, or keep a record
comparing versions: it asks whether this engine was evaluated since the window
opened, and that is in the workflow's own run history, well inside retention
for a weekly window. **A rule about causes would need a state store; a rule
about activity needs a query.**

**So one condition is left gating the cron**, which is the triage above: until
the known findings are quarantined or fixed, every firing is red for reasons
recorded days earlier, and a cron that is always red communicates nothing.

#### 4.18.4 Two extractions this needed, and one duplication it caused

The ladder moved into `evaluate-engine.yml` and the engine-separation cases
into `mqc_uni_engine_jobs.py`, which `mqc_uni_workflows.py` had outgrown at
1034 lines against the thousand-line ceiling.

**Writing the support module and leaving the originals in place duplicated
them.** Six workflow readers existed twice until pylint's duplicate-code check
reported it, which is the drift a support module exists to prevent: a case
comparing against a stale copy of a reader reports about the copy.
`workflow_support.py` owns them now and both modules import them.

| New | Holds |
|---|---|
| `evaluate-engine.yml` | The ladder, taking the engine as an input |
| `evaluate-<engine>-weekly.yml` | One caller per engine, each with its own concurrency group and no cron |
| `mqc_uni_engine_jobs.py` | `115709`, and the three helpers that read the topology |
| `workflow_support.py` | The readers both case modules share |

### 4.19 A gate workflow per target, because a workflow run still aggregates

Added 2026-10-03, superseding the calls section 4.17.3 put inside one gate.
That change gave each engine its own **job**; the instruction is that each needs
its own **workflow**, and the reason is the same one that moved the weekly
ladder: a workflow run has a conclusion, and one red job makes the run red.

| Level | Separates? |
|---|---|
| The check in a pull request | Yes, already: `graded on openai` is its own check |
| **The workflow run** | **No.** Two engines passing and one failing is a red run, and the run is what a reader looks at |
| Required checks in branch protection | Per job, so this part already worked |

So two models passing and one failing reported a red gate, which is the problem
one job reported before the calls were split, moved up one level.

#### 4.19.1 The unit is a target, not an engine

The separation axis is **what is under test**, and that is an engine at a model
version rather than an engine. Two versions of one engine are two subjects:
asking whether the newer one still passes what the older one passed is a
backward-compatibility question, and it is answered by comparing two targets
rather than by one job that measures whichever version the roster names today.

| Target | What it answers |
|---|---|
| `gemini` at its rostered model | How that model behaves now |
| the same engine at the next model | **Whether the next one is compatible** with what the current one passes |

**Naming the workflows per target is what makes that an addition rather than a
redesign.** A version becomes another caller, exactly as another engine does.

**What it still needs, and this is recorded rather than built.** The roster is
keyed by the adapter name: `adapter_for` looks an engine up in the adapter
registry, so `engines.yaml` cannot carry two entries for one adapter today.
Expressing two targets on one adapter needs an entry that names its adapter
separately from its key, which is a roster change and an
`extensibility_standard.md` section 3.4 question. **Until then a target is an
engine**, and the workflows are named so that changing it is a rename rather
than a restructure.

#### 4.19.2 Each gate is self-contained, and that is the cost

A per-target gate runs the resolver, the lint gate, the preconditions and its
own graded bands. **It does not depend on another workflow having passed**,
because a gate that waits on a different workflow run is not independent, and
`workflow_run` reporting does not attach to a pull request the way a push does.

| | |
|---|---|
| What repeats | The resolver, the lint gate and the preconditions, which measure **our** code and are engine-independent |
| What that costs | Jobs, not quota: every repeated job is deterministic, needs no credential and runs in about a minute |
| What it buys | A target's gate answers "is this target's result trustworthy" end to end, with nothing to cross-reference |
| When the repetition is loud | A genuine precondition failure reports once per target. Three reds stating one true fact is noise, not misdirection |

**The alternative was considered and rejected.** Keeping lint and preconditions
in a shared workflow and having the per-target gates depend on it reintroduces
exactly the coupling the split removes: a shared red would stop every target,
which is correct, but a shared **flake** would too, and the targets would no
longer be independently re-runnable.

#### 4.19.3 Adding a target, and the hand-maintained list that made it silent

**grok was rostered on 2026-10-04 and nothing here noticed.** The roster gained
a fourth engine, it was priced, its recording run completed, and this repository
continued to gate three targets. No check failed, because the list of targets
these checks walk was a tuple in the case module:

```python
_ROSTERED_ENGINES = ("gemini", "openai", "claude")
```

**Its own comment claimed it was the roster** — "the engines the roster
carries" — and it was a copy of the roster as it stood when the line was
written. The sibling helper `engine_roster()` already reads the installed
harness and its docstring already states why: a second copy drifts toward
whichever repository was edited last. This module kept one anyway.

**So the check for "every rostered target has its own workflow" could only fail
for an engine somebody had already remembered to add here.** That is the
project's recurring shape once more: the mechanism was right and nothing
established it was reachable for the case it existed to catch.

| | |
|---|---|
| What the tuple is now | `tuple(engine_roster())`, read from the installed harness package |
| Why insertion order is kept | The roster is ordered and the gate's calls chain in that order; a set would lose it |
| What that changes | Rostering an engine makes this repository red until the engine has a gate caller, a weekly caller and a credential offer |

**Three things, and the third is the one that would have been missed.** A live
leg whose credential is absent refuses at preflight (section 4.17.2), which is
correct and is reported as our configuration rather than as a finding. It is
also quiet: the weekly caller exists, the run starts, and the result is a skip
nobody asked for. `evaluate-engine.yml` offers every provider's key explicitly,
so a new engine needs a line there, and `MQC_CAS_UNI_115710` now requires the
variable each rostered adapter declares to be among them.

**The credential's value is not this repository's business.** The offer is a
reference to a secret; the secret lives in the `live` environment behind a
required reviewer, and section 4.17.2 already governs what happens when it is
absent. What is checked here is that the wiring exists, which is the part a
roster addition forgets.

#### 4.19.4 A known finding still blocks its gate, and that is the decision

**Decided 2026-10-05 by the project owner.** A P0 or P1 graded failure fails its
target's gate whether or not the finding is already catalogued. The gates for
all four engines are therefore expected to be red, and `MQC_EVL_EVAL_134205`
alone makes every one of them red at P1.

**The alternative was available and was declined.** `config/findings/<engine>.yaml`
already carries every finding with its reproduction, so an expected-failure
mechanism keyed on that register was a small change: the gates would turn green
and a red would mean something new. That is the more conventional pipeline and
it is the wrong one here.

| | |
|---|---|
| What the register would buy | A green badge, and a red that means a regression |
| What it would cost | **The result stops being visible in the thing that measured it.** A reader would see green and have to be told where the findings are |
| Why that matters now | The findings are being filed with four vendors, and the gate that reports them is the evidence |

**A red gate is a finding, not an unfinished pipeline**, and that distinction is
carried by the README rather than inferred: harness CI green, preconditions
green, model gates red, each with the band that failed and a replay command that
needs no credential. **An evaluation suite whose job is to find defects in
somebody else's product has no reason to present a green badge while it is
holding 24 of them.**

**The trigger for revisiting this is publication, not a date.** Once the
findings are filed with each vendor and the write-up is out, the register-keyed
quarantine becomes the right mechanism: at that point the findings are public,
attributed and tracked elsewhere, so the gate's job changes from reporting them
to detecting the next one. Until then the quarantine is deliberately unbuilt,
and this subsection is why — not an omission anybody needs to rediscover.

**This does not relax the schedule condition in section 4.18.3.** A gate is read
by somebody who just pushed, so a red with a known cause is informative. A cron
firing weekly into nobody's attention is not, and it stays withheld.

## 5. Governance Parity With The Harness

**One project spans two repositories.** The same authors write cases here and
harness code there, and a rule enforced on one side only is a rule that holds
until somebody moves a file. The split was a change to where code lives, not to
what it has to satisfy.

| Rule | Enforced by | Shared how |
|---|---|---|
| Naming, line length, variable length, docstrings | `.pylintrc` at `fail-under=10.0` | Byte-identical file in both repositories |
| Annotation presence on every parameter and return | `cmn.code_standards.annotation_gaps` | One implementation, called with each root |
| PEP 563 prohibited, PEP 649 laziness relied on | `cmn.code_standards.future_annotation_imports` | As above |
| SPDX header, position and identifier | `cmn.code_standards.header_problems` | As above, called with each repository's licence |
| Execution flags and their accepted values | `cmn.pytest_support.add_mqc_options` | One registry, called from both conftests |
| Priority to Allure severity | `cmn.pytest_support.label_priority_severity` | As above |

### 5.1 The checkers are parameterised, not copied

The only difference between the two enforcements is the licence identifier:
Apache-2.0 there, MIT here. **Copying the checkers to state that one difference
would be two implementations of one rule**, and the copy would drift toward
whichever repository was edited less often. They therefore take a root and a
licence, and each repository supplies its own.

This is the same reasoning that gives the option registry two callers rather
than two definitions, and the failure taxonomy one registry rather than a copy
per repository.

### 5.2 `.pylintrc` is the one file that is duplicated, and deliberately

It is configuration for a tool that reads it from the repository root, so it
cannot be imported. The duplication is therefore forced rather than chosen, and
it is marked as such at the top of both copies.

**What makes it safe is that the patterns it carries are not authored here.**
They are normative in the harness `docs/design/test_taxonomy.md` section 2.1, so
the file is a transcription of a specification rather than a second opinion, and
a divergence is a transcription error that the shared test naming would surface
immediately.

### 5.3 Prose rules are referenced, never copied

`.claude/rules/` lives in the harness. `CLAUDE.md` here names those documents as
normative and states only this repository's deltas, because `framework-rules.md`
section 4.1 forbids a second registry and a governance document is a registry of
rules.

**The mechanical enforcement is shared code, so prose drift cannot produce
behaviour drift.** That is the property worth having: a rule restated slightly
differently in two places is a documentation defect, while a rule *enforced*
differently in two places is a defect that ships.

---

## 6. Debugging A Case Without Touching CI

Added 2026-09-23. The harness carries `diagnose-on-demand.yml` and
`debug-failures-on-demand.yml`; this repository carried only its gate, so the
side where graded cases actually live had no way to run one case and look at it.

### 6.1 Separate workflow, separate jobs, no verdict

A debug run is a **separate workflow** rather than an input to the gate. Its
jobs are its own, so nothing it does can contribute to, cancel or colour a gate
run on the same commit.

| Property | Debug run | Gate run |
|---|---|---|
| Selection | One test or a subset, hand-typed | Everything |
| Verdict | **None** | Yes |
| Artifact prefix | `scratch-`, which the collector does not match | `mqc-reports-` |
| Status check | None reported | Reported |
| Judges a failed case | **Yes** | No |

**A hand-typed selection yields no verdict**, for the reason
`testing-standards.md` section 3.3 gives: it is arbitrary, has no backstop, and
a verdict from one would be a partial verdict presented as a full one. The three
independent exclusions the harness applies to its own debug runs apply here
unchanged.

### 6.2 Both refs are inputs, because the pairing is what is under suspicion

Section 3C resolves the harness ref from the case branch, which is right for a
gate and wrong for debugging. **The common debugging question is whether a case
fails against one harness and passes against another**, and a mapping that
answers it automatically cannot be used to ask it.

| Input | Default | Used for |
|---|---|---|
| `case_ref` | The dispatching ref | Running a stabilization or expansion branch of cases |
| `harness_ref` | Whatever the mapping resolves | Pinning the other side to a known commit |
| `tests` | Required | The one case or subset under suspicion |

**The green gate does not apply to a debug run.** Refusing to debug against a
harness that is not green would withhold the tool exactly when it is needed,
which is when something is broken. The run records what it used and yields no
verdict, and those two facts together are what make that safe.

### 6.3 A debug run judges a failed case, and that is the point

The gate does not judge a case whose assertions failed. Invoking a judge on a
case that has already failed costs a request for information that changes no
outcome, and `tier3_evaluation.md` section 4.2 makes skipping it the default for
that reason.

**Debugging is the case where the information does change something.** A failed
assertion says the case did not pass. It does not say whether the case is wrong
or the model is wrong, and those prompt entirely different fixes:

| What the rubric shows | Likely fix |
|---|---|
| Good content, failed a shape assertion | The assertion or the case is wrong |
| Content that was poor as well | The model is wrong |

So a debug run passes `--judge-on-failure`, and the gate never does.

### 6.4 A judged run spends quota, including in replay

**This corrects a claim made elsewhere.** `testing-standards.md` section 2 says
replay jobs consume no quota and are pure CPU. That is true of the **candidate**
response, which is replayed from a stored fixture. It is not true of the judge.

There is no judge fixture. `FixtureKey` is `(case_id, engine, observation_index)`
and keys the candidate only, so a bound judge is a **live call whatever the
mode**. A replay run that judges therefore spends quota, and a replay run that
judges on failure spends it on exactly the cases that failed.

| Run | Candidate | Judge | Spends |
|---|---|---|---|
| Gate, replay | Fixture | Skipped on failure | Nothing |
| Debug, replay, judging | Fixture | **Live** | One request per failed case |
| Live schedule | Live | Live | Both |

**The cost is deliberate and bounded here**, because a debug run is manually
dispatched against a named subset. It is stated rather than left implicit,
because the alternative is a reader trusting a blanket claim that replay is
free and being surprised by a bill.

**Whether the judge should itself be replayed is an open design question**, not
something this section decides. Replaying it would make a replay run fully
deterministic and fully free, which is what replay is for, and would need a
second fixture kind keyed by judge engine as well. Recorded here so it is a
decision on the record rather than a silence.


---

## 7. The Three-Job Attribution Ladder

Added 2026-09-24. A graded run has two moving parts, the candidate and the
judge, and a single job that moves both can only report that something changed.

**Each job holds everything fixed except one thing**, which is the same
principle the repository split was built on and the same one
`diagnose-on-demand.yml` applies to code and fixtures.

| Job | Candidate | Judge | A failure means | Blocks | Credentials |
|---|---|---|---|---|---|
| 1 | fixture | fixture | **Our code** changed a frozen outcome | Yes | **None** |
| 2 | fixture | live | **The judge** moved | No | Judge only |
| 3 | live | live | **The model** moved | No | All |

The fourth quadrant is refused rather than run: a stored score describes a
specific response, so replaying one against a newly generated response answers
a question nobody asked (`tier3_evaluation.md` section 5A.5.1).

### 7.1 Job 1 can now live in the gate, which it could not before

Until judge fixtures existed, a graded gate meant **a live judge call for every
case whose assertions passed**. That is quota on every push, a verdict that
could differ between two runs of one commit, and a credential inside the
workflow A1 keeps credential-free.

With both sides replayed, job 1 is deterministic, costs nothing and needs no
secret, so **the gate grades**. That is the payoff of the judge fixture and the
reason it was worth building.

### 7.2 They run in sequence, and a red job stops the ladder

Job 2 needs job 1 green, and job 3 needs job 2 green.

**A failing job 1 means our code changed a frozen outcome.** Running the judge
live after that spends quota to rediscover something already established, which
is the reasoning `framework-rules.md` section 1 uses for preconditions gating
the graded layers, applied one level up.

**The verdict decides, not the test count.** Each job computes the real verdict
over its own observations, so the same P0 and P1 rules and the same skip
ceilings apply at every rung. What changes is only what a red verdict
attributes to.

### 7.3 Where each job runs, and why not all three in one place

`gate-on-change.yml` names no environment and references no provider secret,
which is A1's guarantee made structural. Jobs 2 and 3 need credentials, so they
cannot live there.

| Workflow | Jobs | Trigger |
|---|---|---|
| `gate-on-change.yml` | 1 | Every push and pull request |
| `evaluate-live-weekly.yml` | 1, then 2, then 3 | Weekly, and on dispatch |

**Job 1 runs in both, deliberately.** In the gate it is the gate; in the weekly
run it is the precondition that decides whether spending quota is worth it. It
is free, so running it twice costs nothing and removes the need to reason about
a result carried between workflows.

### 7.4 What job 2 reports, and what calibration adds

Job 2 re-judges stored responses with the live judge and compares the verdict.
It also runs **calibration**, because the two answer different halves of one
question.

| Signal | Says |
|---|---|
| Verdict moved under a live judge | The drift changed an outcome |
| Exemplar scored away from its anchor | The judge no longer means what the scale says |

**Only the second can say which judge is right**, because an exemplar is
known-correct by construction and neither of two verdicts is. A job reporting
the first alone would tell an operator that something moved and leave them
without a way to decide what to do about it.

### 7.5 A red job 2 does not refresh anything

**Drift that changes no outcome** is recorded, and the judgements may be
refreshed. **Drift that changes an outcome** is not: the stored judgements stay
authoritative, job 1 keeps working, and the new judge is quarantined until the
rubrics are recalibrated.

Auto-refreshing there would silently rewrite what a pass means and break every
historical comparison with nothing saying so. **Direction is reported**, because
a harsher judge manufactures model regressions and a softer one hides real ones,
and the two corrupt the record in opposite directions.


### 7.6 Every rung resolves the harness, and the spending ones most of all

Added 2026-09-24, correcting the section above. Section 7.3 named the two
workflows and said nothing about how each obtains its instrument, and the
weekly workflow was written installing the harness without resolving it.

**Section 3.1 step 3 applies to every workflow that executes cases**, not only
to the gate. It was stated there as a property of the gate because the gate was
the only workflow at the time, and the wording carried that accident forward.

| Workflow | Spends | Consequence of an unresolved harness |
|---|---|---|
| `gate-on-change.yml` | Nothing | A red instrument produces a red gate, and somebody looks |
| `debug-cases-on-demand.yml` | On request | A named subset, already outside the durable record |
| `evaluate-live-weekly.yml` | **Every rung that is not rung 1** | **Quota spent to measure a model with an instrument nobody verified** |

**The argument is strongest exactly where it was missing.** A gate running
against a red harness wastes a few seconds of runner time. The weekly run
spends provider quota, and the findings it produces are attributed to the model
under test, which is the misattribution the resolve job exists to prevent.

**Rung 1 is the precondition for spending, so it is also where resolution
belongs.** One resolve job feeds all three rungs, and every rung installs the
same commit by SHA. Resolving per rung would let the harness move between
rung 1 and rung 3, which would put a verified rung and an unverified one in the
same ladder and silently break the attribution the ladder is built on.

**A red pairing stops the ladder before rung 1.** An ungated gate run still
yields an artifact marked ungated, because a free run producing a marked result
costs nothing. An ungated live run has nothing to offer in exchange for the
quota, so it does not start.


---

## 8. The Operator Runbook

Added 2026-09-24. `docs/running_jobs.md` is the whole operating procedure for
starting a debug or stabilization run. **A tester does not read a design
document to dispatch a job**, which is a requirement rather than a courtesy: a
procedure that costs a design read is a procedure people work around.

### 8.1 It is separate from this document on purpose

This document says why the green gate exists, what a refusal means and which
quadrant is incoherent. None of that is needed to run three cases against a
harness branch, and mixing the two produces a page that answers neither
question well.

| Document | Answers | Read when |
|---|---|---|
| `consumer_ci.md` | Why the gate refuses, what a verdict requires | Changing the pipeline |
| `running_jobs.md` | Which workflow, which inputs, what comes back | **Starting a run** |

**Each repository carries its own.** The harness names no consumer, so it
cannot point at this one, and the workflows differ anyway. There is nothing
duplicated between them to drift.

### 8.2 A runbook that names an input nobody accepts is worse than none

**The failure is silent and it lands on the person least able to diagnose it.**
A dispatch naming an input the workflow does not declare is rejected by GitHub
with a message about the input, and a reader following the documented procedure
concludes the procedure is broken rather than the page.

`MQC_CAS_UNI_115504` reads every fenced command in `running_jobs.md`, extracts
the workflow and the inputs each one names, and requires that the workflow
exists and declares every input. It is the same obligation `115704` places on a
workflow installing the harness, applied to prose instead of to YAML.

**Prose is checked here for the same reason data is checked elsewhere.** This
project has twice shipped a document claiming an enforcement that did not
exist, and a reader who believes a page stops looking.


### 4.4 A pull request takes its target's strictness

Added 2026-09-24, correcting a hole in section 3.

`gate-on-change.yml` resolved the pairing from `github.head_ref`, so a pull
request was evaluated with **the source branch's** strictness. A pull request
from a stabilization branch into `main` therefore resolved the stabilization
entry, which is advisory, and could run ungated, yield no verdict, and merge.
**Code could land on `main` having never been measured with an established
instrument.**

**Merging into `main` means `main`'s rules apply.** Stabilization conforms to
`main`, not the other way around, which is what makes `main` a branch anybody
can roll back to.

#### 4.4.1 The ref and the strictness come from different ends

They answer different questions, so they resolve from different branches.

| Question | Answered by | Because |
|---|---|---|
| Which harness does this run against | The **head** branch | The work knows what capability it needs |
| How strict is the verdict | The **target** branch | The destination sets the bar it will accept |

A push resolves both from the same branch, because there is no other end.

**Strictness is the stricter of the two, never the looser.** An advisory head
merging into a strict target takes the target's strictness; there is no
arrangement in which a pull request is more permissive than either end alone,
which is the property that stops the rule being routed around.


### 4.5 The dependency cascade applies here too

Added 2026-09-24. The cascade is implemented in the harness
(`cmn_verdict_and_cli.md` section 10.28) and reaches this repository through
`cmn.pytest_support`, which `conftest.py` already delegates every hook to.

**It is what makes the security ordering expressible.** `model_evaluation_test_plan.md`
section 4 assigns P0 to four security cases and P1 to three more; the elaborate
cases below them presuppose those results, and running an elaborate case after
its foundation failed reports one defect twice.


### 4.7 The obfuscated payloads are guarded as code points

Added 2026-09-24. `115009` loads the shipped corpus through the real loader and
asserts the obfuscation payloads still carry the code points they are made of.

**These are the first data in the project whose meaning is not its text.** A
zero-width joiner and a Cyrillic small letter o are invisible and
indistinguishable respectively, so a corrupted payload looks correct in every
diff, every review and every editor.

| Payload | What must survive | Why nothing else would notice |
|---|---|---|
| `154105` | Zero-width characters between the letters | They render as nothing |
| `154106` | Cyrillic letters inside Latin words | They render identically to Latin |
| `154104` | A base64 blob that decodes to the override | It decodes or it does not |

**The canary assertions cannot catch this.** They are ASCII and would keep
passing against a mangled payload, which is precisely the failure mode: the
fixture goes on working and stops saying whether it still does. `115009`
decodes the base64 and counts the code points, so a corruption is a failure
rather than a silence.

**It also pins the vectors.** Each payload must still match the registered
vector it was written for, which is the two-screen cross-check
`MQC_EVL_UNI_114608` depends on.


### 4.8 A graded evaluation rule carries a rubric

Added 2026-09-24. `115010` covers the corpus half of `tier3_evaluation.md`
section 4D.3.

**Omitting a rubric now decides something**, so it has to be visible. A rule
serving an `EVAL` case exists to be judged: its requirement is about response
quality, and quality is what a rubric measures. A tool or security rule
legitimately carries none, because those families are decided by deterministic
checks and a rubric there would never run.

**The check belongs here rather than in the harness**, for the reason
`CLAUDE.md` gives: the harness owns no case data, and which family a rule
serves is a fact about this corpus.


### 4.9 The plan and the matrix are compared here too

Added 2026-09-25. `115600` is the parity of `MQC_CMN_UNI_112229`, which the
harness has had since the matrices were written and this repository did not.

**Thirty-nine requirements were traced and stated nowhere.** They existed only
as rows in `rtm_model.csv`, so the requirements this repository promises could
be read only by opening a CSV and reconstructing them. Nothing reported it,
because the check that would have lived on one side of the split.

**Both directions, as the harness does it.** A requirement stated and never
traced is uncovered; a requirement traced and never stated is a claim nobody
wrote down. The second is the one that hid here, and it is the quieter of the
two: a matrix row looks like completeness.


### 4.10 The matrix is compared against the suite, not only against the plan

Added 2026-09-26, found while reconciling the inventory before the first commit.

**`115010` was inventoried in section 4.8, traced by `MQC_REQ_CAS_CI_0019`, cited
by `mqc_tool_compliance.py` and by the test plan as the thing that permitted
their rubricless rules — and never written.** Three documents and a matrix row
described a check that did not exist.

**Section 4.9 could not see it.** `115600` compares the matrix against the plan,
and here the two agreed with each other; neither of them is the suite. The
harness has had `MQC_CMN_UNI_112313` for this direction since the matrices were
written, and it scans the harness's own tests.

| Direction | Catches | Where |
|---|---|---|
| Stated, never traced | An uncovered requirement | `115600` |
| Traced, never stated | A claim nobody wrote down | `115600` |
| **Traced, never implemented** | **A row that reads as completeness** | **`115601`** |

**It reads parsed syntax rather than source text**, because this repository
quotes case identifiers inside docstrings — including the two that quoted
`115010` while it did not exist. A regex would have found those mentions and
called the case present.

**It found five more on its first run.** `115100` to `115104` were renamed and the
matrix kept the old behaviour slugs, with `115102` present under both its old and
its new name. Those are stale references rather than missing tests, and they are
repointed.


### 4.11 The README's own figures are checked

Added 2026-09-26, alongside `MQC_CMN_UNI_112323` in the harness, for the same
reason and on the same day.

**Every figure on the front page had drifted, and one was not a number.**

| Claimed | Actual |
|---|---|
| 66 graded cases | 69 |
| 67 requirements | 71 |
| 47 preconditions | 49 |
| 6 corpora, 43 tasks | 7 corpora, 65 tasks |
| Graded cases "designed, not yet written" | **All 69 written** |

**The last row is why this is a check rather than a correction.** A stale number
misleads a reader about size; a stale claim misleads them about whether the work
exists. Anyone reading that line would have concluded this repository shipped no
graded cases.

**It recomputes rather than storing the numbers a second time**, because the
second copy is what drifted. Case counts come from the design inventories,
requirements from the matrix's rows, graded cases from the parsed test modules,
and corpora and tasks from the data files themselves.

---

## 9. The Findings Register

Added 2026-10-04 at the project owner's instruction. **The gates are red because
the models fail, and that is the project working**: per-engine replay stands at
gemini 2, openai 8 and claude 10, every one a `QC_LLM_*` or `QC_SEC_*` finding
about a third party.

**Nothing is filed with a vendor until the implementation is complete.** What
this register exists for is the interval: a finding observed today may be fixed
upstream before anything is filed, and without a record that fix is invisible.
It would arrive as a gate quietly turning green, which is indistinguishable from
a case that stopped testing anything.

### 9.1 What belongs in it, and what does not

| Outcome | In the register |
|---|---|
| `QC_LLM_*` on a graded case | **Yes.** A finding about the model under test |
| `QC_SEC_*` on a graded case | **Yes**, and these are the blocking ones |
| `QC_HARNESS_*` | **Never.** Our code or infrastructure broke, which is a defect to fix rather than a finding to file |
| A precondition failure | Never. It tests the harness, so a failure is ours |

**The taxonomy already draws this line** and the register reads it rather than
restating it: `framework-rules.md` section 4 assigns each family to what it
asserts about, and filing our own defect with a vendor is the error that line
exists to prevent.

### 9.2 It is not quarantine, and the difference is what each one decides

| | Quarantine | The findings register |
|---|---|---|
| Decides | Whether a case's failure exempts the gate | Nothing. It records |
| Can hold a P0 or P1 | **No.** V1 reads the graded population unconditionally, so a blocking finding cannot be exempted | Yes, and those are most of what it holds |
| Expires | On a model change, or after 21 days | Never. A finding is a dated observation, and history is not a backlog |
| Answers | "May this run be green" | "What did we observe, against which model, and does it still happen" |

**A finding in the register has no effect on any verdict.** That is deliberate:
a record that could turn a gate green would be a quarantine with a different
name, and the project owner's requirement is tracking rather than exemption.

### 9.3 It is generated, never authored

**Twenty reproductions written by hand would drift from the first re-run.** The
register is produced from a run by `tools/findings.py`, on the same principle
that makes the matrix `families` column derived: a fact restated by hand is a
fact that rots.

Each entry carries what a ticket needs and nothing a reader would have to
recompute:

| Field | Holds |
|---|---|
| `case` | The full case identifier, which is the stable handle |
| `taxonomy_code` | The root-cause class |
| `priority` | How blocking it is, from the rule set |
| `observed_model` | **The model that actually served it**, not the one requested |
| `first_observed`, `last_observed` | Dates, so an interval is readable |
| `observations` | How many of how many passed, which is what makes an inconsistency claim checkable |
| `expected`, `actual` | The two sentences a ticket opens with |
| `reproduce` | The exact command |
| `status` | `open`, `reported`, or `resolved_upstream` |
| `ticket` | The vendor's reference, added by hand when one is filed |

### 9.5 Filing needs three sources joined, and nothing joined them

Added 2026-10-05, when filing began and the question was "which file do I open".

**The answer was three files per finding, and five for an inconsistency.** The
register carries the claim; it deliberately does not carry the request or the
response, and `tools/ticket_report.py` exists because a person should not have
to assemble those by hand.

| Source | Supplies | Why it is not in the register |
|---|---|---|
| `config/findings/<engine>.yaml` | The claim, the failure class, expected and actual | — |
| `data/tasks/*.yaml` | The prompt, the constraints, the context documents | The corpus is the request; copying it would be a second copy to drift |
| `tests/fixtures/replay/<engine>/<task>/<rule>/*.json` | Every observation's text | A transcript per finding would make the register unreadable and unreviewable |

**The request is reconstructed, not recorded.** A fixture stores a
`request_hash` and never the prompt. That is deliberate — the hash is what
proves a replay answers the same request — and it means the prompt in a ticket
page comes from the corpus the run dispatched, which is the same text by
construction.

**Every observation is shown, never one.** An inconsistency finding is a claim
about variance: "3 of 5 passed" cannot be carried by a single transcript, and a
vendor reading one response would be reading the wrong thing. The page prints
all of them, labelled.

**A deferral is not reported.** A case skipped behind a failed base is a
consequence of a finding rather than a finding, and section 4.14.1 records that
reading. A vendor receives actual defects; the deferral count belongs in the
project's own write-up, where the cost of one defect is the interesting part.

**The pages are generated and untracked.** `reports/` is ignored, as it is for
every other artifact: a tracked page would be a fourth copy of three sources,
stale the moment a recording is added. Regenerate with
`python -m tools.ticket_report`.

**Nothing here affects a verdict**, exactly as section 9.1 says of the register
itself. This is a reporting view, it gates nothing, and it carries no case for
that reason.

### 9.4 Only a live run can detect an upstream fix

**This is the part that is easy to get wrong.** Replay replays our own recorded
responses, so a finding will reproduce from replay forever, whatever the vendor
does. A replay run therefore **confirms the record** and says nothing about the
current model.

| Mode | What re-running answers |
|---|---|
| `replay` | Whether the recorded finding still reads as a finding, which catches our own corpus or harness drift |
| **`live`** | Whether the model **still** does this, which is the only thing that can retire a finding |

**A finding that stops reproducing live is not deleted.** It takes
`status: resolved_upstream`, the date, and the model it resolved against,
because the claim was always about one model and a later model behaving
differently is the finding's outcome rather than its absence.

**A model change alone does not resolve anything.** Quarantine expires on a
model change because an exemption should not outlive the model it was granted
for; a finding is an observation about a model that was true when it was made,
so it keeps its `observed_model` and gains a second observation rather than
losing the first.

### 9.5 What the register does not try to be

| Not this | Why |
|---|---|
| A bug tracker | It holds no assignee, no severity of its own and no workflow. `priority` comes from the rule set and the vendor's tracker owns the rest |
| A history of every run | One entry per finding, updated. The run-by-run record is the artifacts, which carry 90 days |
| The reproduction itself | The `vendor-report` attachment on a failing case holds every call with its request and response. The register names the command and the artifact rather than copying the payloads, which would put prompts and responses into a tracked file |

**The last row is the one worth stating twice.** A finding's full reproduction is
large, it is already published in the artifact, and copying it into a tracked
YAML file would make a diff unreadable and put model output into version
control.
