<!--
SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
SPDX-License-Identifier: MIT
-->
# Code Excerpts Under Evaluation

Specified by `docs/testing/model_evaluation_test_plan.md` sections 4.4.2 and
4.4.3. These files are **data under evaluation, never harness code.**

## Why they carry a `.txt` suffix

They are deliberately defective. A `.py` suffix would put them in the path of
pylint, pytest collection and every editor's autoformatter, and **an excerpt
silently corrected by a formatter leaves every graded case built on it
asserting against an expectation that no longer holds.** The failure would be a
confident wrong verdict rather than an error.

`MQC_CMN_UNI_10171` through `10173` guard exactly that. They are preconditions
rather than graded cases, because a stale fixture is an instrument defect.

## What each one holds

| File | Defect class | Ground truth from |
|---|---|---|
| `top_scorers_syntactic.py.txt` | Syntactic: an unclosed parenthesis | The parser, which names the line |
| `top_scorers_logical.py.txt` | Logical: a discarded `sorted()` result | Execution against known inputs |
| `settle_order_logical.py.txt` | Logical: three required defects, two credited | Execution, so the finding is arithmetic |

**The first two are the same function**, which is what makes the pair worth
having: defect class is then the only variable between them, rather than being
confounded with subject matter, length or difficulty.

## What they must never become

An excerpt is data, and a code comment is exactly where a planted instruction
would sit. They reach the judge through the isolation boundary in
`tier3_evaluation.md` section 3.1 like any other unauthored content.

Do not fix these files. Their defects are the measurement.
