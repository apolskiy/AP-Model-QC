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

### A changelog, and the pairing rule that required it, 2026-10-12

**Added.** This file. The repository had a README and no changelog while its
recorded-response count, its finding totals and its precondition count all
moved, so the record of when each changed was `CLAUDE_LOG.md` alone, which is a
narrative rather than a version history.

**Added.** `MQC_CAS_UNI_115735`, which calls the harness pairing check against
this repository, and `MQC_REQ_CAS_GOV_0005` tracing it.

**Changed.** README figures: 110 preconditions, 123 requirements traced.

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
