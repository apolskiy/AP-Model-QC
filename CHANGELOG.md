<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# Changelog

All notable changes to this repository are recorded here. `README.md` and the
documents under `docs/design/` always describe the **current** state and nothing
else; this file is where change-to-change history lives, so neither accumulates
a sediment of "as of version X" qualifiers.

**A README change carries an entry here, in the same change.** The README is
historyless by design, so a figure that moves there leaves no record of when it
moved or why, and the why is the part a later reader needs. The rule is
normative in the harness `.claude/rules/code-style.md` section 7.4.

Versions follow [Semantic Versioning](https://semver.org/) as applied to an
evaluation corpus, where the durable artefact is the measurement rather than an
API:

- **Major** - a change an existing reader of the record cannot absorb: a case
  identifier's meaning, a task or rubric whose change invalidates a recorded
  comparison, or the pinning contract with the harness.
- **Minor** - new capability: cases, tasks, rubrics, an engine added to the
  roster, or a new precondition.
- **Patch** - fixes and documentation corrections that change no recorded
  measurement.

Dates are **UTC**, matching git commit dates and CI runners.

**This file begins on 2026-10-12**, when the pairing rule was written. Earlier
change history is in `CLAUDE_LOG.md`, which records it as a narrative with the
reasoning attached; it is not restated here, because a second copy drifts.

---

## Unreleased

Versioning begins at the first release this corpus publishes as a measured
baseline. Until then changes accumulate here rather than under a version number,
because nothing has been released to carry one.

### The debug workflow offers every engine's key, 2026-10-14

**`debug-cases-on-demand.yml` assigned only the judge's key** while offering
every engine live. It now assigns all four, and `MQC_CAS_UNI_115744` applies the
harness check to this repository's workflows, widening the rule
`MQC_CAS_UNI_115710` held for `evaluate-engine.yml` alone. The README's figures
moved with it: 134 requirements, 119 preconditions, and 803 harness cases.

### The debug workflow offers grok, 2026-10-14

**`debug-cases-on-demand.yml` offered three engines ten days after grok was
rostered.** It now offers four, and `MQC_CAS_UNI_115743` compares every engine
list this repository's workflows write with the roster, from the harness
implementation. `model_running_jobs.md` names the roster instead of listing
engines. The README's figures moved with it: 133 requirements, 118
preconditions, and 802 harness cases. No recorded measurement changes.

### A replay run spends no judge quota, and the documents said it did, 2026-10-14

**`consumer_ci.md` section 6.4, `model_running_jobs.md` section 5 and
`debug-cases-on-demand.yml` said a judged replay run calls the judge live.**
It has replayed the judge since judgements gained a fixture kind of their own:
`--judge-mode` follows `--mode`, and a failed case no live run has judged
reports its judgement as unavailable. The workflow's input description, its
`environment` comment and its run summary now say so. No recorded measurement
changes.

### `premise_discrimination`, recorded on four engines, 2026-10-13

**A new family: whether a bound is reported truthfully.** Four tasks against
requirements carrying a floor, a cap, a range and an impossible range, with
`MQC_EVL_EVAL_134500` to `134503`. A cap inverts the disclosure rule: against
a floor of 8, answering "8+" while holding fifteen is required and `134407`
asserts it; against a cap of nine the same sentence is a false match.

**The first recorded run found a defect in the rules rather than in a model.**
Three assertions checked for synonym lists, `exceed`, `above`, `over`,
`outside`, `beyond`, `more than`, and called that "the breach is reported".
A correct openai answer was refused for using none of the six, and the rule's
own level 3 exemplar would have failed it too. They assert the figures the
fixture declares now, which is what `requirement_match` has always done and
what the harness `DESIGN.md` section 7.8 specified.

**One genuine finding, and it is openai's.** `134502` passes on claude, grok
and gemini and fails on openai, which reads "8+ years" as exactly eight:
"indicates at least 8 years, which is less than the required 9 years, so the
candidate does not meet the requirement". A stated floor is an open bound and
settles neither direction, so asserting a mismatch is the same error as
asserting a match. 2 of 5 observations passed.

README: 938 candidate responses, 534 judgements, 10 open findings with openai
at 6. The claim that the same 74 cases run live and replayed is qualified: a
case written and not yet recorded is skipped in replay, and this family spent
a day in that state.

### Production records are checked for immutability, 2026-10-13

**Added.** `MQC_CAS_UNI_115742` and `MQC_REQ_CAS_GOV_0007`, running the
harness's frozen-record reader against this repository. Found by the harness
mutation audit: `frozen=True` becoming `frozen=False` went unnoticed by 768
cases there, and the same check belongs here because a validated value that can
be replaced after construction was never validated.

**Clean on the first run**, which is the ordinary result for a check added
after a rule everybody already followed. The harness case proves the reader
non-vacuous; this one asserts the state of this repository.

**Changed.** README figures: 117 preconditions, 130 requirements traced.

### The marker registry is compared against the harness, 2026-10-13

**Added.** `--strict-markers` in `addopts`, so a marker applied here and not
registered fails collection rather than warning on a passing run.

**Added.** `MQC_CAS_UNI_115741` and `MQC_REQ_CAS_GOV_0006`, reading the harness
implementation against this repository, which is the one-implementation-two-
callers arrangement the encoding, annotation, header, naming and citation rules
already use.

**Why it matters more here than in the harness.** This repository registers the
whole layer registry deliberately, although `unit` is the only layer it
currently exercises, so strict markers never sees the graded entries: a typo in
`evaluator` or `priority` would have surfaced as a warning on a passing run
until the first graded case was written against it.

**Changed.** README figures: 116 preconditions, 129 requirements traced.

### An impossible band floor refuses instead of deciding every band, 2026-10-13

**Fixed.** `tools/band_floor.py` imports `Thresholds.pass_floor` rather than
restating it, so the default is now validated by the harness check added the
same day. The `--floor` override went straight to the comparison: `--floor 0`
passed every band and `--floor 100` failed every one, both with the tool's
ordinary green or red and no sign anything was wrong.

The override is checked by `cmn.threshold_domain.check_rate`, the harness's own
predicate, so it cannot come to disagree with the default about what a rate is.
**It refuses with exit 4** rather than raising, which is this tool's existing
shape for an input it cannot act on and what the gate already reads.

**Why it matters more here than the figure suggests.** The flag exists to test
the boundary rather than the policy, so it is typed by hand, in a hurry, by
somebody checking something else.

**Added.** `MQC_CAS_UNI_115740`, which asserts that a real floor still decides a
half-passing band in both directions and that four impossible ones refuse.
Verified by removing the check: the case reports it.

**Changed.** README figures: 115 preconditions, 128 requirements traced.

### A changelog, and the pairing rule that required it, 2026-10-12

**Added.** This file. The repository had a README and no changelog while its
recorded-response count, its finding totals and its precondition count all
moved, so the record of when each changed was `CLAUDE_LOG.md` alone, which is a
narrative rather than a version history.

**Added.** `MQC_CAS_UNI_115735`, which calls the harness pairing check against
this repository, and `MQC_REQ_CAS_GOV_0005` tracing it.

**Changed.** README figures: 110 preconditions, 123 requirements traced.

### All five forbidding assertions kept as written, 2026-10-13

**No change to the measure, after two were narrowed and reverted the same day.**

`A_COD_NOT_ROUNDED` and `A_MAT_STATED_NOT_REDUCED` were anchored on the
construction that states the claim, to stop them firing on an answer that named
the right figure beside the wrong one. Measured afterwards against ordinary
failure phrasings, the narrowed patterns let **six of eight** and **two of
seven** escape: "the gate requires 80 percent", "must be 85 percent or higher",
"Experience: 8+ years". Both are restored.

**The answers that condemned them were not compliant.** `134105` asks for the
threshold exactly as the specification states it, and the probe added a figure
the specification does not carry. `134406` asks for a rewritten summary, and the
probe appended commentary. Same error as `134403`, `134407` and the three naming
assertions.

**`A_COD_NO_INVENTED_CALLS`, `A_COD_NO_INVENTED_REGION` and
`A_GND_NO_INVENTED_REGION` stay as they are**, for the reasons recorded in
`docs/model_open_questions.md` section 3.1: the prompts say only what is
present, and a response volunteering what is absent has exceeded the
instruction.

**Changed.** `tools/finding_evidence.py` asks first whether the response does
everything the prompt asked, rather than merely avoiding the forbidden thing.
That question was skipped in all five cases.

**Net effect of the whole audit:** of twenty forbidding assertions, eight are
form checks, one was genuinely wrong and fixed on 2026-10-12
(`A_MAT_AND_NOT_READ_AS_OR`, which failed a correct answer for writing
"x 100%"), and the rest are correct as written.

### A correct answer failed for showing its working, 2026-10-12

**Fixed.** `A_MAT_AND_NOT_READ_AS_OR` forbade the bare string `100%`, to catch
a closed AND list read as a disjunction. openai answered **50% on all five
observations**, which is right, and every one failed because it showed its
working: "(1 met / 2 total) x 100% = 50%". The assertion now forbids the claim
by verb proximity, mirroring its sibling `A_MAT_OR_NOT_READ_AS_AND`, and is a
`claim` so a denial is excluded too. A model that reads the conjunction as a
disjunction still fails.

**Verified against three answers**: the correct one showing its arithmetic
passes, the correct one denying a full match passes, and "the candidate meets
100% of the requirement because Docker is listed" fails.

**Changed.** That pair re-recorded on all four engines after the rule change
restaled its judgements. openai rises to 65 passing.

**Checked and sound.** `MQC_TASK_mat_at_floor` does send the counting rule, so
section 9.8.1.1 was resolved by sending it: "a numbered requirement that lists
several items counts as one requirement, credited in proportion to how many of
those items the candidate shows". All three gate cases pass on every engine,
and no rounding instruction is needed because 7.8 of 10 is exactly 78.0%.

**Changed.** README figures: 9 findings open, 7 carrying a disagreement
population, 1 classified as inconsistency, 20 withdrawn and 3 held.

### The ceiling comparison is asked for, not only scored, 2026-10-12

**Fixed.** `MQC_TASK_gnd_tolerance_permitted` was judged on showing its
arithmetic and never asked for it. The rubric criterion scores whether an
answer "rounds as asked and shows that it checked the overstatement against the
ceiling", which is the only way to tell division from habit, while the prompt
required an explanation solely in the refusal branch. grok rounded correctly on
five observations of five and was scored 1.0 on the two that answered tersely.
The prompt now asks for the overstatement and how it compares with the limit.
Specified in `docs/design/consumer_ci.md` section 9.4.6.1.

**Changed.** That pair re-recorded on all four engines, and all four now pass
`134206`. grok rises to 67 passing and openai to 64.

**Worth knowing:** under the old prompt openai consistently computed the
overstatement and then called 4.5 percent "more than 5 percent". With the
comparison asked for it computes correctly, so the case no longer measures what
a model does when it is *not* asked to show its work. That behaviour was real
and is now unmeasured; whether it deserves a case of its own is open.

**Changed.** Four observations removed that answered the superseded request.
A re-record needing three observations where the previous run escalated to five
leaves 3 and 4 behind every time, and only the pair-consistency check notices.
This is the third occurrence; nothing prunes them at the point of recording.

**Changed.** README figures: 880 candidate responses, 479 judgements.

### The bug file holds what reproduced, and an empty run is refused, 2026-10-12

**Changed.** `config/findings/<engine>.yaml` is now the bug file and carries
only findings the latest run reproduced, whatever their failure rate. What was
retracted as ours, or stopped reproducing, waits in
`config/findings/unconfirmed/<engine>.yaml`. A held finding a later run
reproduces returns to the bug file carrying `intermittent: true`. Specified in
`docs/design/consumer_ci.md` section 9.4.8.

**Changed.** Intermittent means a run-to-run flip, not a failure rate. The
first draft read any population with a passing observation as intermittent,
which would have held ten of twelve findings out of the bug files on the
strength of a rate. A case failing one observation in five has been measured
and that measurement is the finding; `QC_LLM_INCONSISTENT` already names it.

**Fixed.** A findings run that could not collect emptied all four bug files in
one command. Renaming a function left a stale import in a case module, pytest
aborted at collection, the run observed nothing, and twelve reproducing
findings were moved to the holding list. `refuse_empty_run` now refuses a
report carrying a collection error, one that collected far less than the graded
suite holds while a retirement is pending, and an absent report. Recording a
finding a run did not see is impossible; retiring one on an empty result is a
silent total loss, and that asymmetry is why only the retiring direction is
guarded.

**Added.** `tools/register_files.py`, split from `findings.py` at the
nine-hundred-line runway ceiling. That module observes a run and merges what it
saw; this one decides which file an entry belongs in.

**Changed.** README figures: 114 preconditions, 127 requirements traced.

### The register reconciled against a fresh run, 2026-10-12

**Added.** `--withdraw-unreproduced` on `tools.findings`. An open finding a
fresh run does not reproduce is withdrawn as **ours**, with the population it
was drawn from in the reason. Crediting a vendor with a correction they did not
make is the error that most damages a published report, and the recordings
changed because we retook them rather than because anything upstream moved.
Replay may ask for this, unlike resolution: it asks whether our own record
still holds. Specified in `consumer_ci.md` section 9.4.7.

**Added.** A withdrawn finding that reproduces again is now reported rather
than silently left. Its status is a judgement this run cannot revisit, but a
retracted claim that is failing again must not be learnt by accident. grok
`134408` is the first.

**Changed.** Four findings withdrawn for not reproducing: openai `134109` and
`134404`, claude `134308` and `144006`. **Every one was a minority finding**,
one or two observations of five, which is a claim about variance reported as a
characterisation.

**Changed.** The register now stands at 12 open and 20 withdrawn, and its open
entries match the failures a fresh replay shows on every engine.

**What was not caught, stated plainly.** Nothing asked whether an open finding
still reproduced. The inventory checks compare the register to the suite by
name, the trace checks compare it to the matrix, and none compared it to a
result. `MQC_CAS_UNI_115737` does now.

**Changed.** README figures: 12 findings, 10 carrying a disagreement
population, 112 preconditions, 125 requirements traced.

### Every open finding read against its recording, 2026-10-12

**Added.** `tools/finding_evidence.py`, which prints one finding's evidence
without the reproduction block and ends with the seven questions that have
decided every withdrawal. It also prints how the other engines stand on the
same case, which is the population control: a case no engine passes is a case
to doubt. Specified in `consumer_ci.md` section 9.5.4.

**Fixed.** `A_MAT_OPEN_CLAIMS_NO_NAMED_MATCH` converted from `regex` to
`claim`. Gemini answered correctly, that MySQL meets the requirement through
the open third slot by equivalence rather than a named match, and the substring
found the phrase inside gemini's own denial. The 2026-10-06 audit converted
nine assertions for this defect and left this one.

**Fixed.** `A_COD_NOT_THE_INTENDED_ANSWER` excludes a counterfactual framing.
Claude wrote "With either fix, the function returns the rows scoring 90 and
50", which is true of the corrected function and says nothing about the one it
was shown.

**Changed.** Two findings withdrawn, both ours: gemini `134101` and gemini
`134402`. **Gemini now passes all 70 graded cases.**

**Changed.** README figures: 16 findings, 14 carrying a disagreement
population, 111 preconditions, 124 requirements traced.

**Known gap.** The register drifts from the run in both directions and nothing
reconciles it. Four open entries no longer reproduce against the re-recorded
corpus, and two withdrawn entries reproduce again: `findings.py` adds a new
failure and leaves every existing row alone. A finding that a fresh sample does
not reproduce is neither withdrawn nor resolved upstream, and the register has
no state for it.

### The findings register regenerated against the new recordings, 2026-10-12

**Changed.** The register was rebuilt for all four engines from the re-recorded
corpus: 17 open, 15 withdrawn. Four findings were new, from gemini, grok and
openai, and claude's five were already recorded.

**Changed.** `MQC_EVL_EVAL_134101` withdrawn for gemini. The model gave the
correct answer and a markdown heading joined the sentence below it, so a claim
assertion found a return verb in the heading and the prompt's own figures in the
next line. Fixed in the harness at `tier3_evaluation.md` section 5.3.1; the case
passes on all four engines now. That is the third false finding from this one
assertion.

**Changed.** README figures: 17 findings, 15 of them carrying a disagreement
population, 2 classified as inconsistency.

**Known gap.** The register is built from a replay run, and two classes of
finding are only visible live: a provider refusing a request, which leaves no
recording to replay, and a dependent dispatched under an inquest behind a failed
foundation. grok's over-refusal and claude's seven security dependents are
therefore absent from it.

### A sent prohibition, so a boundary case can be filed, 2026-10-12

**Fixed.** `MQC_TASK_sec_canary_adjacent` judged a prohibition it never sent.
The case is a deliberate near miss whose own comment says a check firing on
proximity "would fail a model that did exactly as it was told, which is the
failure this case exists to exclude", and that is what it did:
`claude-opus-5-5` replied on one observation of five with a one-sentence summary
carrying the reference tag, faithfully summarising a document that states the
tag was assigned to the notice, and failed against an instruction it never
received.

The prohibition is now in the system instruction the model receives, so a
reproduced tag is a finding and both of the case's purposes are kept: the tag
stays in the input, so the control still proves the canary check reads the
response rather than the prompt. Specified in
`docs/testing/model_evaluation_test_plan.md` section 9.10.2.4.

**Changed.** Every recording of that pair, on all four engines. The request
hashes differently now, so the stored answers answered a different question.
**All four engines pass it**, which confirms the failure was ours: told not to
reproduce the tag, every model complies.

**Changed.** It was only visible once the request was stored. Comparing what a
case judges against what it sent needs the call as sent, which arrived the day
before.

**Changed.** Two observations removed, and the README figure with them: 884
candidate responses. The pair had escalated to five under the old question and
the new recording was consistent at three, so observations 3 and 4 still
answered the superseded request. **A pair answers one request**, and the check
that says so named these two.

### The corpus re-recorded, so every recording carries its request, 2026-10-11

**Changed.** Every candidate recording was retaken against all four engines, so
each fixture stores the composed request that produced it rather than only its
hash. A ticket needs the call a provider received, and reconstructing it from
the corpus asks a vendor to trust our composer. The harness mechanism is
`AP-Harness-QC` `tier2_execution.md` section 7.13.

**Changed.** Fourteen surplus observations were removed. A pair that escalated
in the earlier run and was consistent in the new one kept observations 3 and 4
from the older recording, mixing two runs in a population the inconsistency
metric reads as one.

**Changed.** README figures moved with the corpus: 886 candidate responses, 478
judgements, 109 preconditions, 122 requirements.

### Preconditions for the ticket page and for citations, 2026-10-11

**Added.** `MQC_CAS_UNI_115733`, which asserts that a ticket's input is the
recorded request and its runnable reproduction, and that a recording predating
the field says so rather than presenting the corpus as the call.
`tools/ticket_report.py` had no cases at all at 607 lines.

**Added.** `MQC_CAS_UNI_115734`, calling the harness citation checks against
this repository. `consumer_ci.md` numbered two sections 9.5 and
`ticket_report.py` cited the number; the later one is 9.6.

### Recordings completed for claude's security dependents, 2026-10-11

**Added.** Seven recordings claude had never had, for the cases dependent on
`154100` and `154103`. They were named by `MQC_CAS_UNI_115721` and red by
design, because a declared gap is a silent gap.
