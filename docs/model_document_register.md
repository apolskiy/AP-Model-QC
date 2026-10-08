<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->

# Document Register

**Every tracked document in this repository, and what it holds.** Added
2026-10-04 at the project owner's instruction, after a design document in the
harness was found to have fallen behind the changes made around it.

**This is the list a documentation review works through.** A document absent
from the list a reviewer holds is a document nobody reviews, which is the
failure this register exists to prevent rather than to describe.

**It is checked in both directions.** `MQC_CAS_UNI_115413` reports a tracked
document this register does not name, and a path this register names that is not
there. The check is the harness's, called with this repository's root: one
implementation, two callers, as the encoding and header rules already use.

**`CLAUDE.md` requires reading this before any work.** A complete list nobody
opens prevents nothing.

## Specifications

| Document | Holds |
|---|---|
| `docs/design/consumer_ci.md` | This repository's CI topology: the gate and weekly workflows per engine, harness pinning and branch pairing, the debug workflow, artifact keying |

**The harness holds the rest.** This repository owns cases and data, not
architecture, so there is no module design here. `DESIGN.md` and the tier
designs live in `AP-Harness-QC` and are **never copied in**, per `CLAUDE.md`.

## Test planning

| Document | Holds |
|---|---|
| `docs/testing/model_evaluation_test_plan.md` | Every evaluation requirement, the graded case inventory, the corpus specifications, and the precondition inventory this repository owns |
| `docs/testing/rtm_model.csv` | Evaluation requirements mapped to graded cases, with the **evaluation families** those cases belong to |
| `docs/testing/case_index.csv` | **Generated.** One row per case with its evaluation families and its task's tags, which is the grain `--family` and `--tag` resolve at |

## Operations and record

| Document | Holds |
|---|---|
| `docs/model_document_register.md` | **This file.** Every tracked document and what it holds, checked against the repository both ways |
| `README.md` | **The latest state only.** What the case set is, how to run it, the current figures. Never a history |
| `docs/model_running_jobs.md` | How to run each workflow and what each one spends |
| `CLAUDE_LOG.md` | Decisions and their reasoning in date order, written for an external reader |

**`README.md` and `CLAUDE_LOG.md` divide by time, not by topic.** The README says
what is true now and the log says how it became true and what was learned on the
way. A reader wanting the current figures should not have to read history to
find them.

## Governance

| Document | Holds |
|---|---|
| `CLAUDE.md` | The directive router: what to read, the core directives, the boundary with the harness |

**The rules themselves are the harness's.** `code-style.md`,
`framework-rules.md` and `testing-standards.md` are normative for both
repositories and live in `AP-Harness-QC`, which is why this repository's
`CLAUDE.md` cites them rather than restating them: two copies of one standard
drift.

## Fixture documentation

| Document | Holds |
|---|---|
| `tests/fixtures/excerpts/README.md` | What defect each code excerpt carries and how it is verified, so a fixture's purpose is recorded where the fixture is |

## Renamed documents

**Renamed 2026-10-08**, so an open editor tab says which checkout a file
belongs to (harness `code-style.md` section 7.2). The old names remain in
`CLAUDE_LOG.md` entries that were true when written.

| Now | Former name |
|---|---|
| docs/model_running_jobs.md | was `docs/running_jobs.md` |
| docs/model_document_register.md | was `docs/document_register.md` |

**`consumer_ci.md` was left alone**, naming this repository's role, which is
unmistakable without a prefix. `MQC_CAS_UNI_115718` holds that one exemption
and fails on a second.
