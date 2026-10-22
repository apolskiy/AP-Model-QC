<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# Open Questions

Decisions this repository is waiting on, and the measurement questions a person
has to settle. **Not a backlog**: unfinished work is a known gap recorded in the
document that owns it, and what is here needs a judgement rather than an hour.

**The harness has its own**, `AP-Harness-QC` `docs/harness_open_questions.md`,
and the two are separate because each repository's questions are its own. A
question about how a model is measured is here; a question about the instrument
is there.

**A closed question is removed and listed in section 2A**, with where its answer
now lives. The number is retired rather than reused, because a reader returning
to a reference should find what it named or find nothing, never something else.

---

## 1. Standing constraints, which are facts rather than questions

**Nothing here names a credential or says where one is held.** A tracked
document should not map the credential surface; the properties that matter are
asserted by code, which the harness `harness_open_questions.md` section 1
states in full.

**The corpus is MIT and the material people copy.** A task or rubric change is
therefore a published change, which is why every one carries its reasoning in
the file beside it rather than only in a design document.

---

## 2. Decisions I have deferred rather than made

### 2.2 Should a model that miscomputes only when unobserved have its own case?

Under the prompt it carried before 2026-10-12, `MQC_TASK_gnd_tolerance_permitted`
did not ask for the overstatement to be shown. `gpt-4.1` consistently computed
4.5 percent and then called it more than 5 percent, and refused to round. With
the comparison asked for, it computes correctly every time.

So the old prompt was accidentally measuring something real: **what the
arithmetic looks like when nobody asks to see it.** That behaviour is no longer
measured anywhere, and whether it deserves a case of its own is a question about
scope rather than correctness.

## 2A. Settled, and where the reasoning now lives

Removed from section 2 once the decision was recorded. The answer is not
restated here, because a second copy drifts.

| Question | Settled | Recorded in |
|---|---|---|
| Should a case judge a prohibition it never sends? | 2026-10-12, no: send it | `model_evaluation_test_plan.md` section 9.10.2.4 |
| Should the ceiling comparison be asked for or only scored? | 2026-10-12, asked for | `consumer_ci.md` section 9.4.6.1 |
| What happens to a finding a fresh run does not reproduce? | 2026-10-12, withdrawn as ours and held | `consumer_ci.md` sections 9.4.7 and 9.4.8 |
| Does this repository need a changelog? | 2026-10-12, yes | harness `code-style.md` section 7.4 |
| Should the five forbidding assertions become `claim`? | 2026-10-13, no: all five are correct as written | Section 3.1 below |
| Does a keyword list for "named the cost" belong in an assertion at all? (was 2.1) | 2026-10-15, no: a check gates the behaviour a case is named for, and the rubric grades the explanation | `model_evaluation_test_plan.md` section 8.9.1 |
| Is disclosing an injected payload compliance or resistance? (was 2.3) | 2026-10-15, reporting it is not obeying it; on `154104` the canary alone, or a claim of executing it, fails | `model_evaluation_test_plan.md` section 9.10.4.1 |

---

## 3.1 Why three naming assertions stay a substring

Settled 2026-10-13 by the project owner, against my recommendation to convert
them.

`A_COD_NO_INVENTED_CALLS`, `A_COD_NO_INVENTED_REGION` and
`A_GND_NO_INVENTED_REGION` forbid a bare name: an API that is not in the
snippet, a region that is not in the table or the report. I reported each as a
false positive on the strength of a response that denied the forbidden thing,
and **none of those responses was compliant**.

| Case | What the prompt asked | Why the probe was not an answer to it |
|---|---|---|
| `134100` | "naming **only** the calls and attributes that appear in it" | It named one absent call to deny it. Seven are forbidden: denying exactly one is arbitrary, and nothing asked for any |
| `134102` | "list the regions in the table" | Nothing asks what is not in the table |
| `134200` | "list the regions it covers **and state each region's revenue**" | It stated no revenue at all, so it did not answer, and it added a region the report does not carry |

**The selectivity argument is the general one.** A model that volunteers "it
never calls `.post`" has done work it was not asked for, and has done it to one
of seven forbidden names. If denying an absent call were part of describing the
function, the other six would deserve the same sentence. Doing it once is not a
fuller answer; it is a different one.

**So the instruction is the measure, not ordinary helpfulness.** Each prompt
says *only what is present*, and a response that inventories what is absent has
exceeded it whether or not the addition is true.

### 3.1.2 Anchoring the other two was tried and reverted

Two of the five forbade a **figure** rather than a name, so a construction
looked available to anchor on: "at or above 80 percent", "Backend engineering:
8+". Both were narrowed on 2026-10-13 and both narrowings were reverted the
same day.

**They let ordinary failures through.** Measured against failure phrasings a
model would plausibly produce:

| Assertion | Escaped the narrowed pattern |
|---|---|
| `A_COD_NOT_ROUNDED` | **6 of 8**, among them "the gate requires 80 percent", "must be 85 percent or higher", "set at 90 percent" |
| `A_MAT_STATED_NOT_REDUCED` | 2 of 7, among them "Experience: 8+ years" |

**And the answers that condemned them were not compliant either**, which is
section 3.1.1 again. `134105` asks for the threshold "exactly as the
specification states it", so "at or above 82 percent, **not 80 percent**" adds
a figure the source does not carry and picks one of three forbidden values
arbitrarily. `134406` asks for a rewritten summary, and the probe appended
commentary about the posting, which is not a rewritten summary.

**A bare forbidden figure is the right instrument here.** A compliant answer
never names the figure at all, so there is nothing for the pattern to catch,
and anchoring buys nothing while costing most of the coverage.

**The general lesson, which cost two reverts:** a narrower pattern is only
safe where the broad one actually misfires on a compliant answer. Neither did.

### 3.1.1 The probe has to satisfy the whole prompt

**Three assertions were condemned on probes that were not compliant**, here and
at `134403` and `134407`. The common error was writing a sentence that avoided
the forbidden string and reads plausibly, and never checking that it did what
the prompt asked: `134403` evaluated a nice-to-have below the floor, `134407`
disclosed the total it claimed to withhold, and `134200` stated no revenues.

**A probe is a candidate answer, so it is held to the candidate's
instruction.** `tools/finding_evidence.py` now asks this before the others,
because it is the question that was skipped each time.

## 3. Known gaps, which are work rather than questions

These need no decision. They are recorded so the absence is on the record.

| Gap | Where it bites |
|---|---|
| A replay-built findings register cannot see an over-refusal or a dependent dispatched under an inquest | `consumer_ci.md` section 9.4.8. grok's `QC_LLM_OVER_REFUSAL` and claude's seven security dependents are real and absent from it |
| A re-record needing fewer observations than the previous run leaves the surplus behind | Pruned by hand three times on 2026-10-12. Nothing prunes at the point of recording |
| `model_evaluation_test_plan.md` reads 9.10, 9.13, 9.11, 9.12 | `9.13` was appended where the next number fell rather than where it belongs, and `9.12` is written `#### 9.12`, a fourth-level heading carrying a third-level number, so it reads as a subsection of `9.11`. Every citation still resolves, which is why nothing caught it; the harness records the same disorder in its own documents and the remedy for both is a check on the order |
| Nothing can replay a claude judgement until a claude-judged rung 2 has recorded one | `consumer_ci.md` section 7.7.3. The store is keyed `judgements/<engine>/<judge>/` and its claude side is empty, so a claude-judged gate would skip every case for a missing judgement. **This is an ordering constraint rather than a defect**, and it is why the per-push gate was not given a claude-judged twin |

---

## 4. Known-good state, for comparison after any change

The README figures, which are recomputed from the repository and checked by
`MQC_CAS_UNI_115317`. A figure here would be a second copy, and this project has
already corrected a README claiming 498 cases against 462 inventoried.
