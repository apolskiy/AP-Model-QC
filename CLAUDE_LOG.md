<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# AP-Model-QC Decision Log

The running record of decisions made in this repository and the reasoning behind
them, written for an external reader.

**Harness decisions are logged in the harness.** This file records what is
decided *here*: which harness a case branch runs against, what the cases assert,
and the boundary between the two repositories as it is met from this side.

---

## 2026-09-23: This Repository Gains A CI Gate, And Refuses An Unverified Harness

### The problem a pin does not solve

`pyproject.toml` pinned `ap-harness-qc @ git+...@main`. `pip` resolves that to
whatever the branch head is at install time and has no notion of whether the
commit passed anything. **A red harness main would become the instrument
silently**, and every finding produced with it would be attributed to the model
under test.

This repository also had **no workflows at all**, so nothing ran here on a push.

### What was built

* **`config/harness_pin.yaml`**: the branch-to-harness mapping, carried on the
  branch. `main` pairs with harness `main` and requires green; `stabilization`
  pairs with harness `stabilization`; `extend/*` pairs with harness
  `stabilization` because the capability those cases need exists nowhere else
  yet; `expand/*` pairs with `main`.
* **`tools/harness_pin.py`**: resolves the pairing to a **commit**, asks whether
  that commit's `gate-on-change.yml` concluded success, and refuses when it must.
  It imports nothing from the harness, because it runs before the harness is
  installed and a check fetched from the harness would be asking an unverified
  ref to vouch for itself.
* **`.github/workflows/gate-on-change.yml`**: a `resolve` job ahead of Gate 1,
  then lint and preconditions on both platforms, each installing the **SHA**
  that resolve produced rather than a branch name.
* **`docs/design/consumer_ci.md`**: the design, with the inventory.
* **`.pylintrc`, `CLAUDE.md`, `conftest.py`**: governance and wiring, so the
  rules apply here exactly as they do in the harness.

### Decisions

* **The pin in `pyproject.toml` becomes a floor, not a pairing.** It is what a
  clone installs when nothing resolves a pin, and `main` is the right default
  precisely because `main` is the branch required to be green.
* **Absence of a run is never a pass.** A commit with no run is the normal state
  of a branch pushed seconds ago, and treating it as green is how an unverified
  harness becomes the instrument.
* **Required on `main`, advisory elsewhere.** An advisory run proceeds
  **ungated** and yields no verdict. Refusing everywhere would block case
  stabilization precisely while the harness is being stabilized.
* **`extend/` versus `expand/` is declared, not inferred.** Whether a case needs
  a harness extension is a fact only its author knows.
* **Governance is referenced, never copied.** The harness rule documents are
  normative; the *enforcement* is shared code (`cmn.code_standards`,
  `cmn.pytest_support`) so prose drift cannot produce behaviour drift.

### A defect found by running it

The resolver was run against the real harness before its `stabilization` branch
existed. It raised, and the traceback exited **1**: the one code this must never
produce, because exit 1 means a suite measured something and it failed, which CI
reads as the model underperforming. A harness branch that does not exist is the
opposite of a finding about a model.

Fixed to refuse with **4** on any branch, advisory or not: strictness governs
whether an *unverified* harness may be used, and cannot govern whether a
*nonexistent* one may be, because there is no commit to install. Recorded as
`consumer_ci.md` section 3.8 and `MQC_CAS_UNI_10422`.

### State

22 cases passing, Gate 1 at 10.00/10, one workflow, 17 cases inventoried in
`consumer_ci.md` section 4 and five in the test plan section 8.

---

## 2026-09-23: The Instruction-Following Corpus

The first authored evaluation data. Six tasks and six rule sets covering
`MQC_REQ_MDL_INS_0001` through `005`, which the nine graded cases `30001` to `30009`
will run against.

### What was authored

| Task | Covers | Device |
|---|---|---|
| `ins_format_stated` | INS_001 | A stated JSON format instruction |
| `ins_format_absent` | INS_001 | **The ablation.** Same material, instruction removed |
| `ins_quantities` | INS_002 | Four quantitative and form ceilings at once |
| `ins_ordering` | INS_003 | Measurables before the rest |
| `ins_prohibition` | INS_004 | A prohibited glyph |
| `ins_combined` | INS_005 | Every constraint competing for one output |

**One source document is shared across the family** so a difference in result is
attributable to the instruction rather than to the material. It is deliberately
dull: the family measures obedience to shape, and interesting content would give
the model reasons to depart from it.

**The ablation is the measurement.** `30001` and `30002` differ only in whether
the format instruction is stated. Without the control, a model that returns JSON
out of habit scores as instruction-following.

**Assertions decide, the rubric grades inside them.** An instruction either was
or was not followed, which is not a judgement call and is deliberately not left
to a model. Each rubric scores something a check cannot: whether the bullets
still say anything once the ceilings are met, whether the prose reads naturally
without the prohibited glyph.

### Two authoring failures worth recording

Neither was catchable by a schema test, and both produced a clean refusal, which
is the loader behaving correctly and the corpus being wrong.

**A wrapper key where the loader wanted a bare list.** `tasks:` at the top level
became an unknown field on the first record. The refusal is the right one: a
tolerated wrapper would have loaded zero tasks and reported success.

**A YAML flow mapping whose commas were read as key separators.**
`{description: Changes dropped, or the ordering ignored entirely.}` parsed as two
keys, and the second was not `description`. Block style throughout now.

### `count` and `ordering` promoted in the harness

The corpus authored seven constraints across the two kinds, which is the
repetition `tier1_ingestion.md` section 8 says triggers promotion. Neither fits
a registered kind: a bullet ceiling is a bound on how much rather than output
shape, and a response can satisfy every shape constraint while ordering its
content wrongly.

**A third candidate was refused in the same pass.** The corpus initially carried
`form` for capitalization and sentence completeness. Those *are* output shape, so
it was collapsed into `format`: the registry stays small by refusing kinds a
registered one already covers, and a vocabulary that grows with every author's
phrasing describes nothing.

### Three guards, and what the third one is for

`10423` runs the real loaders and integrity checks over the shipped files. The
harness has 88 cases proving the loaders work and none saying whether this
corpus loads.

`10424` holds this repository to the registered constraint vocabulary. The
harness warns rather than failing, by design, and a warning nobody reads is how
a vocabulary fragments.

**`10425` protects the ablation, and it was verified against the case that
matters.** Adding a constraint to the control task alone is caught by R3. Adding
a constraint **and** a matching check satisfies R2 and R3 both: integrity passes
cleanly, the control is destroyed, and `10425` is the only thing that fails. That
was tested rather than asserted, because the whole claim is that the design
intent is invisible to the schema.

### What this does not yet include

**No graded cases and no replay fixtures.** A graded case runs in replay by
default, and a fixture is recorded from a live run. Recording needs
`GEMINI_API_KEY` and spends quota, so it is the user's call rather than
something to do unasked. The data is complete and verified; the cases and their
fixtures are the next step.

### State

25 cases passing, Gate 1 at 10.00/10, 35 requirements traced.

---

## 2026-09-23: The Grounding Corpus, And A Rule I Broke Writing It

### What the user corrected

I wrote `data/tasks/grounding.yaml` before documenting or tracing it. The
standing rule is documentation, then traceability, then code, and the reason is
the iteration: where implementation meets something the design did not
anticipate, the design is corrected first and the code follows.

The file was held back as a draft, the corpus inventory was written, the
traceability rows were added, and only then did it land. The rule is now
normative in two places rather than assumed: `.claude/rules/testing-standards.md`
under **Authoring Order**, and `.claude/skills/skill-rules.md` under **Phase 3
Is A Loop, Not A Finish Line**.

**Why it matters here specifically.** Writing code first produces documentation
that describes what was built rather than what was intended, and a design
written afterwards cannot disagree with the code, so it can never reveal that
the code is wrong. Which is exactly what happened next.

### Six invented taxonomy codes

Authoring the grounding rules, I wrote `QC_LLM_ALTERED_VALUE`,
`QC_LLM_UNSUPPORTED_CLAIM`, `QC_LLM_CONTEXT_IGNORED`,
`QC_LLM_VERIFIABLE_FALSEHOOD`, `QC_LLM_INCOMPLETE_ANSWER` and
`QC_LLM_CONSTRAINT_VIOLATION`. **None is registered. The registry already
carried the right code for every one of them.**

**Nothing was checking.** `MQC_CMN_UNI_10143` through `10145` verify that every
code a design document names and every code the harness emits is registered.
Neither reads a data file, and a `taxonomy_code` in a golden rule is exactly
that: a code this corpus attaches to a finding, chosen by an author.

The invented codes were **plausible**, which is what made it a defect rather
than a typo. `QC_LLM_ALTERED_VALUE` reads like a registered code and means what
`QC_LLM_SOURCE_ALTERATION` means, so findings would have split into two buckets
where there is one population.

**`QC_LLM_CONSTRAINT_VIOLATION` was the worst of them.** It collapsed three
distinctions the taxonomy draws deliberately, so a bullet ceiling breach, an em
dash and an ignored ordering instruction would all have reported as one kind of
failure. Correcting it was not a rename: each assertion was reassigned by what
it actually breaches, against the meanings in `test_taxonomy.md` section 6.1.

| Breach | Code |
|---|---|
| A quantitative ceiling | `QC_LLM_LENGTH_VIOLATION` |
| A prohibited character | `QC_LLM_FORMAT_VIOLATION` |
| An ignored instruction | `QC_LLM_INSTRUCTION_DRIFT` |
| JSON structure or required keys | `QC_LLM_SCHEMA_VIOLATION` |

`MQC_CAS_UNI_10426` now reads every `taxonomy_code` in every rule file against
`registered_codes()`. It was documented and traced before it was written, and it
failed on first run naming all six, which is how the corpus was corrected.

### The grounding corpus

Six tasks across `MQC_REQ_MDL_GND_0001` to `005`, against one quarterly report with
four regions and exact figures.

**Grounding is measured against a source**, which is why it is a separate
corpus: instruction following can be judged from the answer alone and this
cannot. **The figures are exact by design**, because a figure is checkable by
string match, which turns "did the model alter a stated value" from a judgement
into an assertion, and the judge is itself a model.

**A fabrication target is designed in**: the report names four regions and says
nothing about a fifth. **`GND_003` uses a source that contradicts the obvious
assumption**, so a model answering from prior knowledge gives the opposite
answer and context use becomes observable rather than inferred.

**`GND_005` is an asymmetric pair and the asymmetry is the requirement.**
Understating a sourced figure is permitted where a conservative floor is asked
for; overstating is not. The second task deliberately *instructs* the model to
round up, so a model that complies has followed an instruction at the cost of
the source. That is why `30015` is P1 and `30014` is P2.

### State

26 cases passing, Gate 1 at 10.00/10, 38 requirements traced, 2 corpus families.

---

## 2026-09-23: The Ambiguity Corpus, And A Guard That Grew Into A Rule

Three tasks across `MQC_REQ_MDL_AMB_0001` to `003`. Documented and traced before
written, per the authoring order.

### A second ablation pair, running the opposite way

The instruction-following pair varies whether an instruction is **given**. This
one varies whether the input is **answerable**. Both tasks carry the same
standing instruction to ask when something is unclear, and differ only in
whether anything is unclear: one change request names neither which threshold
nor what value, its twin names both and says what to leave alone.

**Neither task alone measures the requirement.** A model that always asks passes
`AMB_001` and fails `AMB_002`; one that never asks does the reverse. The
requirement is discrimination, and that is why the registry carries
`QC_LLM_AMBIGUITY_UNHANDLED` and `QC_LLM_OVER_CLARIFICATION` as separate codes
rather than one code for getting it wrong.

### `AMB_003` puts the new matching code to work

Availability is 99.1 against a 99.5 gate, and the longest incident is 41 minutes
against a 60 minute ceiling. **One gate fails and one holds, deliberately**: a
model warning about both has not read the readings, which the rubric scores.

Two failure modes, two codes:

| Failure | Code |
|---|---|
| Proceeds with no warning | `QC_LLM_MATCH_MISCOMPUTED`, a gate outcome not following stated semantics |
| Warns without naming the gate or the margin | `QC_LLM_INSTRUCTION_DRIFT` |

"Warned but uselessly" and "did not warn" call for different fixes, so they are
not one finding. This is the first use of `QC_LLM_MATCH_MISCOMPUTED`.

### The control guard became a rule over a property

`MQC_CAS_UNI_10425` was written against one named task. A second ablation pair
made that a liability: the new control would have been unprotected, and nothing
would have said so.

It now asserts over **every task tagged `control`**, with the population derived
from the corpus rather than named in the test. The identifier and behaviour name
are unchanged, because the case still asserts what it always asserted; what
changed is where the population comes from.

**It carries an expected count.** Deriving the population from a tag means a
control that loses its tag silently leaves the population, and the checks would
then pass over a smaller set while reporting nothing. The count turns that into
a failure.

Verified by injecting a constraint into the **ambiguity** control, which no line
of the test names, and confirming it fired.

### State

26 cases passing, Gate 1 at 10.00/10, 40 requirements traced, 3 corpus families,
15 tasks, 15 rule sets, referential integrity clean.

---

## 2026-09-23: The Requirement Matching Corpus

Ten tasks across `MQC_REQ_MDL_MAT_0001` to `004`, the largest family and the one
`QC_LLM_MATCH_MISCOMPUTED` was registered for. Documented and traced before
written; the arithmetic was computed and checked before it was written into a
design document, because that is where an error would have hidden.

### The gate boundaries are hit exactly

Section 3.2 of the test plan requires a threshold to be tested **at** its value
rather than near it. One posting carries ten mandatory and five nice-to-have
requirements, and three resumes land on the three rows of the decision table:

| Case | Mandatory | Combined | Outcome |
|---|---|---|---|
| `30022` | 7.0/10 = 70.0% | Not computed | Warn, name the cutoff, skip the optional set |
| `30023` | 7.8/10 = **78.0%** | 12.8/15 = **85.3%** | Proceed |
| `30024` | 9.0/10 = 90.0% | Not consulted | Proceed |

**The 7.8 is a fractional credit, not a rounding.** One mandatory line is a
five-item closed AND list of which the candidate holds four, worth 0.8 of that
single line. It is the only way a ten-requirement posting reaches exactly 78,
and it is the specified arithmetic rather than a fixture convenience.

**`30023` clears by three tenths of a point**, which is the point of it. The
design records that two real postings at 78% mandatory with every nice-to-have
met landed at 84.9% and 84.3%, both just failing. A fixture that cleared
comfortably would not be testing the boundary.

**`30022` asserts an absence.** A model reporting a nice-to-have percentage
after failing the mandatory cutoff has done work it was told to skip, and that
is visible in the output: the five optional items are named nowhere in a
compliant answer.

### The connector cases make interpretation observable

`30019` to `30021` hold the candidate fixed and vary only the phrasing, because
the connector decides the arithmetic entirely. The same candidate scores 100%
or 33% on the same line depending only on how the connector was read, so
**reading a disjunction as a conjunction is revealed by behaviour** rather than
needing reasoning to be inspected. Each case asserts the correct figure and
rejects the figure the opposite reading produces.

`30021` is the family's only judged path. No named item matches, so the third
slot engages, and **the disclosure is the requirement**: a report reading
"matched" without saying it was judged makes a soft gate look hard.

### The experience rows differ by who produced the figure

`30025` to `30027` follow the disclosure rule, whose failure codes the design
specifies rather than leaving to an author: `SOURCE_ALTERATION` for rewriting a
stated figure, `OVER_DISCLOSURE` for emitting a calculated total where the floor
was asked for, `AMBIGUITY_UNHANDLED` for proceeding without prompting.

**`30026` is why a numeric fabrication check must be directional.** Stating "8+"
while holding fifteen is true, and the obvious implementation flags that correct
behaviour as a violation. The case asserts both halves: the floor is present and
the full total is absent.

### State

| | Value |
|---|---|
| Corpus families | 4 |
| Tasks | 25 |
| Rule sets | 25 |
| Assertions | 51 |
| Constraints | 32, every one checked |
| Referential integrity | Clean |
| Unregistered kinds or codes | None |
| Cases passing | 26, Gate 1 at 10.00/10 |

Eleven registered codes now carry the corpus, none invented.

---

## 2026-09-23: The Code Comprehension Corpus, And A Hole Found Before Writing

Nine tasks across `30029` to `30037`. The loop caught something this time
**before** any data was written, which is the first time in this session that
has happened rather than after the fact.

### The hole, found while specifying

`ContextDocument` carries inline `content` and has no file reference. A task
supplying a code excerpt therefore holds its own copy of text that already
exists under `tests/fixtures/excerpts/`, where `10401` through `10403` guard it
by parsing and executing it.

**That is two places stating one fact, and the guarded copy is not the one the
model sees.** A fixture repaired by a formatter would be caught; the task file
repaired by the same formatter would not, and every case built on it would
assert against an excerpt the guards never examined.

Three options, and the rejected ones are worth recording:

| Option | Rejected because |
|---|---|
| Add a file reference to `ContextDocument` | A schema and loader change in the harness, against a design specifying hand-authored YAML, to solve a problem a check solves |
| Inline it and accept the duplication | Leaves the dispatched copy unguarded, which is the whole defect |
| **Inline it and check the copies match** | Chosen, and `10428` is it |

**The excerpts are generated from the fixtures rather than retyped**, so the
inlined copy starts identical and `10428` keeps it that way.

### A defect in my own check, found by running it

`10428` first asserted that the number of inlined excerpts equalled the number
of mapped fixtures. It failed: five inlined documents against three fixtures,
because **an excerpt legitimately serves several tasks**. The syntactic one is
dispatched by `30032` and `30035`, since literal preservation and defect
location are different requirements over the same material.

The assertion now tracks **coverage rather than a count**: what must not happen
is a fixture mapped and dispatched by nothing, which would leave it guarded and
unused while the cases built on it assert against a copy this check never saw.

### The family brings no requirements of its own

Step 6 of the registration procedure records that as the expected case rather
than an omission. These nine formulate `GND_001`, `GND_002` and `GND_004` in the
code domain: a grounding requirement is domain-independent, and the point of a
second formulation is that the behaviour survives a change of domain. A model
that stays in source on prose and fabricates against code has not satisfied
`GND_001`, and one formulation could not have said so.

### The recall case puts `QC_LLM_DEFECT_MISSED` to work

`settle_order` carries five defects, three required and two credited. The
required set is graded **conjunctively as an assertion**, so a confident,
well-written explanation naming only the unchecked index fails regardless of how
it reads. That is exactly a miss rather than a misstatement, which is the
distinction the code was registered for.

**Defect 3 is the one the family exists for.** Confirming the coupon is present
establishes only that a subtraction will not raise; it says nothing about
whether the result is a price anyone should accept. The rubric scores whether
the explanation carries the arithmetic through to who ends up out of pocket.

### State

| | Value |
|---|---|
| Corpus files | 5 |
| Tasks | 34 |
| Rule sets | 34 |
| Assertions | 71 |
| Referential integrity | Clean |
| Unregistered kinds or codes | None |
| Cases | 28 passing, Gate 1 at 10.00/10 |

Twelve registered codes carry the corpus. `QC_LLM_DEFECT_MISSED` and
`QC_LLM_MATCH_MISCOMPUTED`, both registered today from the user's examples, are
now in use.

---

## 2026-09-23: The Settlement Case, Corrected By The User

The user read the settlement case and said the three money defects are
deterministic, so the evaluator should settle them and none needs to reach the
judge. Then clarified: the judge still renders its conclusion, but if the
deterministic part is missed the test fails regardless, and the judge's value is
the additional problems it can catch.

**Both statements describe the implementation exactly**, and checking that was
the right first move rather than agreeing. `ObservationOutcome.passed` returns
`False` on a failed assertion before it looks at a score, and
`--judge-on-failure` is how a failing case still gets a judge's view. Nothing
architectural needed changing. What needed changing was the case.

### Three things were wrong, and execution settled all of them

The design drew the required set **by code site**. Drawing it by **outcome**
turns out to be better, because each outcome is produced by calling the function
and comparing the return against the correct settlement:

| Outcome | Call | Returns | Correct |
|---|---|---|---|
| No settlement produced | undefined save code | `KeyError` | 50.0 |
| The seller pays the buyer | coupon of 30 | **-10.0** | 50.0 |
| The goods are free, silently | coupon of 20 | **0.0** | 60.0 |

**The undefined save code was graded by rubric.** It was filed as a credited
defect, and it is as deterministic as the other two. A defect the evaluator can
settle should not be scored by a model.

**The zero settlement was fused with the negative one.** Both were one defect
and one assertion. They are different failures: a negative settlement is visibly
absurd and a reviewer catches it, while **a zero raises nothing, returns a
number, and looks like a successful discount**. That is the one that reaches
production.

**The fixture guard was missing the zero entirely.** `10403` executed the
negative case and both raising cases and never asserted the 0.0, so the outcome
the family exists to catch was not itself under guard.

### The probe found a defect in my own assertion

Three candidate answers were run through the real assertion machinery rather
than reasoned about. The middle one names the negative settlement and not the
zero, which is precisely the answer the split exists to catch, and **it passed
the zero assertion**: the pattern carried a bare `0\.0`, which matches inside
`-10.0`.

| Answer | Credited | Case |
|---|---|---|
| Names only what a linter finds | 0 of 3 | FAIL |
| Names the negative, not the silent zero | **1 of 3** | FAIL |
| Names all three | 3 of 3 | PASS |

The pattern now bounds every alternative and refuses a preceding digit. Without
running it, the split would have been documented, implemented, and defeated by
one unbounded alternative.

### A repair that broke a second thing

The first fix selected its target by searching for a line containing `pattern:`
and `zero`, which matched the **seller-pays** pattern, because that one carries
the phrase "below zero". Both patterns briefly checked for zero words. Caught by
re-running the probe, and the repair now selects by assertion id.

That is the third time this session a shell heredoc mangled an escape; this one
wrote a literal backspace byte into the YAML, which the loader refused with
`QC_DATA_MALFORMED_SOURCE`. The harness behaved correctly throughout.

---

## 2026-09-23: A Debug Workflow For The Side That Needed One

The user described the debug capability: separate CI jobs, one test or a subset,
without affecting CI, on any branch including stabilization. **That capability
existed in the harness and not here**, which is the side where graded cases
live and where debugging a case or a model actually happens. This repository
had one workflow, its gate.

### Three linked gaps, found by following the description

**No debug workflow here at all.** `diagnose-on-demand.yml` and
`debug-failures-on-demand.yml` are harness workflows running harness tests.
Nothing could run one graded case and look at it.

**The judge flag belongs here and only here, which I got wrong first.** I
recorded the harness diagnostic workflows as having a gap because they do not
pass `--judge-on-failure`. Checking rather than assuming: the harness collects
**zero** graded cases, `pytest -m "evaluator or tool or sec"` gathers nothing,
and the consumer fan-out runs preconditions only. There is nothing there to
judge and the flag would be dead configuration. **Those workflows are correct as
they stand.** The real gap was that this repository, where every graded case
lives, had no debug workflow at all.

**`testing-standards.md` claimed replay jobs consume no quota.** True of the
candidate, which is replayed from a fixture. **Not true of the judge**, which
has no fixture kind at all: `FixtureKey` is `(case_id, engine,
observation_index)` and keys the candidate only, so a bound judge is a live call
whatever the mode. A replay job consumes no quota **because the gate does not
judge a failed case**, not because replay makes judging free.

### What the debug workflow does that the gate must not

| | Debug | Gate |
|---|---|---|
| Selection | One test or a subset, hand-typed | Everything |
| Verdict | **None** | Yes |
| Artifact prefix | `scratch-` | `mqc-reports-` |
| Judges a failed case | **Yes** | No |

**Both refs are inputs, and that is the point.** Section 3C resolves the harness
ref from the case branch, which is right for a gate and useless for debugging:
the common question is whether a case fails against one harness and passes
against another, and a mapping that answers it automatically cannot be used to
ask it.

**The green gate deliberately does not apply.** Refusing to debug against a
harness that is not green would withhold the tool exactly when it is needed. The
run records what it used and yields no verdict, and those two facts together are
what make that safe.

**It judges, because that is what separates a wrong case from a wrong model.** A
failed assertion says the case did not pass. The rubric says whether the content
was good and the shape assertion wrong, or the content was poor as well. Those
prompt entirely different fixes, and the gate has no use for the distinction
because it is not fixing anything.

### An open question, recorded rather than settled

Whether the judge should itself be replayed is not decided. Replaying it would
make a replay run fully deterministic and fully free, which is what replay is
for, and needs a second fixture kind keyed by judge engine as well.
`consumer_ci.md` section 6.4 records it as an open design question so it is a
decision on the record rather than a silence.

### Added

`10429` asserts the three exclusions structurally: dispatch-only trigger, an
artifact the collector pattern does not match, and the words in the file. `10430`
asserts that the debug workflow judges and **no other workflow does**, checked
across every file in the directory rather than against a list.

Both were verified by injecting the defect: adding `--judge-on-failure` to the
gate, and renaming the debug artifact to the collector prefix.

### State

30 cases passing, Gate 1 at 10.00/10, two workflows, both YAML-valid.

---

## 2026-09-24: 108 Exemplars, And Six Assertion Defects They Exposed

Step one of three agreed with the user: exemplars first, because calibration is
the only thing that can say **which** judge is right, and it had nothing to work
with. All 108 anchors now carry one.

### Writing them found more than it added

The exemplars were never the point on their own. Running them through the real
assertion machinery found **six defects in assertions I had written**, every one
a false positive or a silent miss against a compliant model.

**Two false positives that would have blamed a compliant model.**

The bullet ceiling counted words **across bullets**, because a regex `\s` matches
a newline. Three compliant nine-word bullets, twenty-seven words in total,
tripped a twelve-word ceiling and would have reported
`QC_LLM_LENGTH_VIOLATION` against a model that obeyed exactly. Fixed by bounding
every per-bullet pattern to horizontal whitespace.

The grounding share check required a percent **sign**, while the prompt asks for
"a percentage" and a model answering in words has complied.

**One assertion that could not tell asserting from refusing.** The overstatement
check rejected "30 million" anywhere, so the best possible answer, which names
the rounding in order to decline it, was marked as having made it. Narrowed to
an assertion-shaped pattern, with the cost stated: a violation phrased far from
the words EMEA or revenue now escapes it, and the positive requirement for 28.7
is what catches the common shape.

**Three silent misses, which are worse.** Sweeping for the percent-sign class
after fixing one instance found eight more, and three of them ran in the reject
direction. `A_MAT_OR_NOT_READ_AS_AND` rejected `33%` and let "33.3 percent"
through, which is precisely the defect that case exists to catch. A false
positive is noisy and gets found; a silent miss looks like coverage forever.

**The lesson recorded: fix the class, not the instance.** I corrected the
grounding percent pattern and moved on, and the identical mistake sat in eight
other places for another twenty minutes.

### A defect in the inserter, not the corpus

The first pass wrote exemplars as folded YAML scalars, which turn newlines into
spaces. A three-bullet exemplar arrived as one line of thirty words and failed
its own word ceiling. The inserter now chooses a **literal** scalar whenever the
exemplar carries line structure, so bullets stay bullets and a line-bounded
assertion sees what a model would actually have produced.

### `10432`, and what it deliberately does not require

A level 5 exemplar must pass the assertions of its own rule. Assertions are
conjunctive gates, so a case awards nothing when one fails: an exemplar claiming
a top score that fails its own gate is incoherent, and calibration would report
drift every time the judge behaved correctly.

**Levels 1 and 3 are unconstrained, and that is deliberate.** It is tempting to
require a bottom exemplar to fail something. The whole reason a rubric sits
beside the assertions is that a response can satisfy every mechanical check and
still be useless, and an exemplar demonstrating exactly that is the most useful
bottom anchor there is. Five of the level 1 exemplars are assertion-clean.

### State

32 cases passing, Gate 1 at 10.00/10, 34 tasks, 71 assertions, 108 anchors all
carrying exemplars, referential integrity clean.

Next: the judge model probed in its own right, then judge fixtures and the
three-job split.

---

## 2026-09-24: Three Words For One Thing, Reduced To One

The user asked whether the corpus should be renamed to a synonym. Measuring
first changed the answer, and two things I had assumed were wrong.

**`corpus` is not my coinage.** It is established harness vocabulary from before
the split: `screen_corpus` is a public function in `ingestion/screening.py`, and
`tier1_ingestion.md` uses it throughout. The blast radius of a rename was over a
hundred sites across both repositories including that public name, not the
handful I had in mind.

**Both obvious synonyms are already taken.**

| Candidate | Collides with |
|---|---|
| `dataset` | `TaskDataSet`, a schema class meaning a **single task record**, used across twelve modules |
| `collection` | pytest, which owns the word here: `pytest_collection_modifyitems`, `--collect-only`, "collected test" |

The first is the sharper objection. `TaskDataSet` is singular and central, so
renaming the aggregate to "dataset" would make the word ambiguous exactly where
it is read most.

**But the instinct was right about something real.** The project had **three**
words for one area: `corpus` in code and design, `data/` on disk, and `DAT` in
requirement identifiers. I introduced the third without checking the first.

### What changed

`MQC_CAS_DAT_*` became `MQC_CAS_COR_*`, seventeen rows. Nothing else moved: no
code, no test names, no directories.

**`data/tasks/` and `data/rules/` keep their names**, because the distinction is
real rather than cosmetic. They hold data; `corpus` is what the loaded whole is
called once the loaders have joined and validated it, which is the distinction
`screen_corpus` already draws.

**`MQC_REQ_CAS_PRE_0001` stays**, because `PRE` names a different axis. It covers the
excerpt fixture guards, which are a precondition rather than a corpus
requirement, so it is not a second word for the same thing.

### The rule this produced

`testing-standards.md` now carries **One Word Per Concept, And A Second One Is
Drift**, with the two rejections recorded as evidence rather than taste: a
synonym that collides is worse than the word it replaces, and a word is only a
better name if it is unambiguous where it will be read.

### One over-report worth noting

The script asserting no stale references flagged the very section explaining the
retirement, which names the old prefix as prose. That is the over-reporting
pattern this project keeps correcting: a live identifier carries a number, and
prose carries an asterisk. Verified directly instead, and no live
`MQC_CAS_DAT_<n>` remains anywhere.

### State

32 cases passing, Gate 1 at 10.00/10, 487 harness tests passing.

---

## 2026-09-24: The Code Corpus Generator Ships

`data/tasks/code_comprehension.yaml` is produced from the guarded excerpt
fixtures rather than typed beside them, and the script that produced it lived
outside the repository.

**That made a shipped property unmaintainable.** `10428` asserts every inlined
excerpt is byte-identical to the fixture it names. When a fixture changes that
check correctly fails, and without a shipped generator the only remedy was to
hand-copy the fixture into the task file and hope the indentation matched. The
check would then pass over a file nobody could reproduce.

`tools/generate_code_corpus.py` now ships, alongside `harness_pin.py`, which is
what `tools/` is for: generators and maintenance scripts, never case code.

### `10433` covers a different failure from `10428`

| Check | Fails when |
|---|---|
| `10428` | An inlined excerpt no longer matches its fixture |
| `10433` | The shipped file is not what the generator produces |

The second catches a **hand edit to a generated file**, which is the failure
that loses work silently: someone corrects a prompt directly, the corpus is
regenerated weeks later, and the correction vanishes with nothing reporting it.
Verified by editing one word of the shipped file and watching it fire.

**`build` returns text and `main` writes it**, so the check exercises the same
code path an author runs. A check that rebuilt the expected output separately
would assert that two copies of one algorithm agree, which is not the claim.

**Only the task file is generated.** The rule file beside it carries exemplars,
reasoning and assertions that no generator produces, so regeneration cannot
clobber them. The split is deliberate: the task file is mechanical because its
content is the fixtures, and the rule file is judgement because its content is
what to check.

### State

33 cases passing, Gate 1 at 10.00/10.
