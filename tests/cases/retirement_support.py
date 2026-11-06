# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code for the retirement preconditions: one mixed report, one open register.

Created: 2026-10-29
Last updated: 2026-11-06

This file contains ``MIXED_REPORT``, a JUnit report carrying one passed case, one
case skipped behind a failure, and that failure; ``open_on_both``, which builds
an open finding for the passed case and the skipped one; and ``replay_run``, which
builds a replay run that measured that report.

**Not collected**, as the filename carries no ``mqc_`` prefix, the same device
``graded_support.py`` uses. Support code defined inside a collected case module is
reported by ``MQC_CAS_UNI_115711``.

**Every retirement case needs the same three outcomes**, because the rule under test
is that absence from a run's failures is not a pass: two of these three cases are
absent from the failures and only one of them was measured.
"""

from datetime import date
from pathlib import Path

from tools.findings import RunContext
from tools.findings_run import parse_passed

MIXED_REPORT = (
    '<testsuites><testsuite>'
    '<testcase name="MQC_EVL_EVAL_134401_passed"/>'
    '<testcase name="MQC_EVL_EVAL_134402_skipped">'
    '<skipped message="QC_HARNESS_DEPENDENCY_UNMET"/></testcase>'
    '<testcase name="MQC_EVL_EVAL_134400_failed">'
    '<failure message="QC_LLM_MATCH_MISCOMPUTED"/></testcase>'
    '</testsuite></testsuites>'
)

PASSED_CASE = "MQC_EVL_EVAL_134401_passed"
SKIPPED_CASE = "MQC_EVL_EVAL_134402_skipped"


def open_on_both() -> dict[str, dict[str, str]]:
    """Build an open finding for the case that passed and the one that skipped.

    Returns:
        dict: The register, by case name. A fresh dictionary each call, because
        removing and resolving both modify the register in place.
    """
    return {
        name: {"case": name, "status": "open", "observations": "1 of 5 passed"}
        for name in (PASSED_CASE, SKIPPED_CASE)
    }


def replay_run(report: Path) -> RunContext:
    """Build a replay run of 2026-11-06 that measured ``MIXED_REPORT``.

    Args:
        report (Path): Where the report is written.

    Returns:
        RunContext: A replay run, not asked to resolve, whose passing cases are
        read from the report.
    """
    report.write_text(MIXED_REPORT, encoding="utf-8")
    return RunContext(
        engine="openai", mode="replay", models={}, expected={},
        today=date(2026, 11, 6), resolve=False, passed=parse_passed(report),
    )
