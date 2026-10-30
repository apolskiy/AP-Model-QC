# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code for the retirement preconditions: one mixed report, one open register.

Created: 2026-10-29
Last updated: 2026-10-29

This file contains ``MIXED_REPORT``, a JUnit report carrying one passed case, one
case skipped behind a failure, and that failure; and ``open_on_both``, which builds
an open finding for the passed case and the skipped one.

**Not collected**, as the filename carries no ``mqc_`` prefix, the same device
``graded_support.py`` uses. Support code defined inside a collected case module is
reported by ``MQC_CAS_UNI_115711``.

**Both retirement cases need the same three outcomes**, because the rule under test
is that absence from a run's failures is not a pass: two of these three cases are
absent from the failures and only one of them was measured.
"""

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
        holding and resolving both modify the register in place.
    """
    return {
        name: {"case": name, "status": "open", "observations": "1 of 5 passed"}
        for name in (PASSED_CASE, SKIPPED_CASE)
    }
