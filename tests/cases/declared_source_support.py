# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code running the shipped no-quote checks, for the cases that check them.

Created: 2026-11-14
Last updated: 2026-11-14

This file contains ``SOURCE_PHRASE_ABSENT``, the assertion kind a no-quote rule
declares; ``declared_checks``, every such assertion in the shipped corpus with
the case declaring it; ``failing_checks``, the checks that fail a given answer
with what each reported; and ``passing_checks``, the checks that pass it. Each
check runs through the harness's own assertion runner with its rule's own
parameters, so a case reads what a graded run would decide.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by ``docs/testing/model_evaluation_test_plan.md`` section 9.10.7.3.
"""

from typing import Any, Final

from evaluation.assertions import run_assertion

from tests.cases.graded_support import shipped_cases

SOURCE_PHRASE_ABSENT: Final[str] = "source_phrase_absent"


def declared_checks() -> list[tuple[str, Any]]:
    """Return every ``source_phrase_absent`` assertion with the case declaring it.

    Returns:
        list: Pairs of case identifier and assertion, in case order.
    """
    return [
        (case_id, assertion)
        for case_id, case in sorted(shipped_cases().items())
        for assertion in case.golden_rules.assertions
        if assertion.kind == SOURCE_PHRASE_ABSENT
    ]


def failing_checks(declared: list[tuple[str, Any]], answer: str) -> list[str]:
    """Name each check that fails the answer, with what it reported.

    Args:
        declared (list): Pairs of case identifier and assertion.
        answer (str): The answer every check reads.

    Returns:
        list: One entry per failing check.
    """
    failing: list[str] = []
    for case_id, assertion in declared:
        result = run_assertion(assertion, answer)
        if not result.passed:
            failing.append(f"{case_id} {assertion.assertion_id}: {result.detail}")
    return failing


def passing_checks(declared: list[tuple[str, Any]], answer: str) -> list[str]:
    """Name each check that passes the answer.

    Args:
        declared (list): Pairs of case identifier and assertion.
        answer (str): The answer every check reads.

    Returns:
        list: One entry per passing check.
    """
    return [
        f"{case_id} {assertion.assertion_id}"
        for case_id, assertion in declared
        if run_assertion(assertion, answer).passed
    ]
