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
| `docs/testing/rtm_model.csv` | 80 requirements, traced |
| `data/tasks/`, `data/rules/` | **7 corpora, 65 tasks**, loading with zero integrity violations |
| `tests/fixtures/excerpts/` | Three code excerpts, with their guards |
| Preconditions (`CAS`, `UNI`) | **63 cases, all passing** |
| Gate 1, pylint at `fail-under=10.0` | **10.00/10** |
| CI | Three workflows: the gate, the live ladder, and debugging on demand |
| Graded cases (`EVAL`, `TOOL`, `SEC`) | **69 written**: 40 evaluator, 21 security, 8 tool |
| Recorded responses | **`SEC` complete**, 63 observations across 21 cases, recorded 2026-09-28 for six cents. `EVAL` and `TOOL` unrecorded, because both spend judge quota as well as candidate quota |

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
