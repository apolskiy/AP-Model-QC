<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# AP-Model-QC: AI Assistant Directives

Welcome to **AP-Model-QC**, the evaluation cases for an automated foundation
model and LLM-as-a-Judge QC pipeline.

**This repository is the cases. The harness lives in
[AP-Harness-QC](https://github.com/apolskiy/AP-Harness-QC)**, which this one
consumes as a pinned dependency. Split 2026-09-23; the harness `DESIGN.md`
section 5.1 carries the boundary and what it cost to find.

## The Rules Are The Harness's Rules

**One project spans two repositories.** Governance is not restated here, because
`framework-rules.md` section 4.1 forbids a second registry and a governance
document is a registry of rules. A rule copied into this file would drift toward
whichever repository was edited less often, and the copy would be wrong silently.

Read these in the harness, where they are normative:

| Document | Holds |
|---|---|
| `.claude/skills/skill-rules.md` | The four-phase pipeline, Git safety, logging |
| `.claude/rules/code-style.md` | Naming, annotations, docstrings, prose, cross-platform |
| `.claude/rules/framework-rules.md` | Module separation, the seven gates, the failure taxonomy |
| `.claude/rules/testing-standards.md` | Test naming, the inventory principle, artifacts |
| `docs/design/harness_test_taxonomy.md` | The single registry of identifiers, priorities and failure codes |
| `docs/design/harness_ci_pipeline.md` | The workflows, the credential boundary, branch topology (section 3C) |

**The mechanical enforcement is shared code, not shared prose.** That is the
property worth having: a rule restated slightly differently in two places is a
documentation defect, while a rule *enforced* differently in two places is a
defect that ships.

| Rule | Enforced by | Shared how |
|---|---|---|
| Naming, line length, docstrings | `.pylintrc` at `fail-under=10.0` | Byte-identical file in both repositories |
| Annotation presence | `cmn.code_standards.annotation_gaps` | One implementation, called with each root |
| PEP 563 prohibited | `cmn.code_standards.future_annotation_imports` | As above |
| SPDX header and identifier | `cmn.code_standards.header_problems` | As above, with each repository's licence |
| Execution flags | `cmn.pytest_support.add_mqc_options` | One registry, two callers |

`docs/design/consumer_ci.md` section 5 states the parity mechanism in full.

## Read The Register First

**`docs/model_document_register.md` names every tracked document in this repository and what each holds.** Read it before any documentation work and work through it on any review: it is the only complete list, and `MQC_CAS_UNI_115413` checks it against the repository in both directions.

**The harness has its own**, and the two are separate because each repository's documents are its own. Harness `harness_test_taxonomy.md` section 12 records why a reading order was not enough: a design document fell behind while being named in one the whole time.

## What This Repository Owns

* **`docs/design/consumer_ci.md`**: which harness this case set runs against,
  and what it refuses to run against. The one design document authored here.
* **`docs/testing/model_evaluation_test_plan.md`** and **`rtm_model.csv`**: the
  model requirements and their traceability. Never copied into the harness.
* **`tests/cases/`**: the cases themselves, and the preconditions guarding their
  fixtures.
* **`tests/fixtures/`**: task data, golden rules, replay fixtures and code
  excerpts. **The harness owns none of this**, and a harness check reading a
  file here is a boundary violation.
* **`config/harness_pin.yaml`**: the branch-to-harness mapping.
* **`tools/harness_pin.py`**: the resolver, which imports nothing from the
  harness by design.

## Deltas From The Harness

These are the only places the two repositories differ, and each is a
consequence of the split rather than a preference.

* **Licence is MIT**, so every tracked file's SPDX header names `MIT`: Python, markdown and YAML alike, written when the file is created rather than in a later pass (`code-style.md` sections 1.1 and 1.2, enforced by `MQC_CAS_UNI_115502` and `115503`). **The corpus matters most here**, being the material this rationale names. The cases
  are material people copy and adapt; the harness is a tool others depend on and
  takes Apache 2.0 for its patent grant.
* **The module code is `CAS`**, and identifiers come from the block
  `115000-115999`, partitioned in the harness `harness_test_taxonomy.md` section 3.2.1.
* **The Allure epic is `AP-Model-QC`**, so a collector reading both repositories
  can tell which produced a result.
* **`conftest.py` is a delegation**, never a second configuration. Every hook
  body lives in `cmn.pytest_support`.
* **CI resolves the harness before installing it.** `gate-on-change.yml` has a
  `resolve` job ahead of Gate 1, because this repository's instrument is a
  dependency and pip has no notion of whether the commit it fetched passed
  anything.

## Core Directives

These restate nothing; they are the harness directives that bite differently
here.

* **Zero Direct Git Commits:** Do NOT execute git commit, git push, or direct
  branch operations. Staging files is permitted.
* **Never Pin By Branch In CI.** The resolver produces a commit, and every
  install step takes that commit. Installing the branch would install something
  no gate has seen.
* **A Case Is Designed Before It Is Written.** Every case appears in an
  inventory in a design document before it exists, is traced in
  `rtm_model.csv`, and carries its category. The harness enforces the same order
  mechanically and this repository holds itself to it.
* **Preconditions Carry No Priority.** They sit above the scale: a failure means
  the graded layers never execute and nothing is measured.
* **Credentials Are Never In Configuration.** They are read from the environment
  at runtime and redacted from every log and artifact.
* **The Cases Own No Harness Code.** A helper that would be useful to the
  harness belongs in the harness, behind its interface.
