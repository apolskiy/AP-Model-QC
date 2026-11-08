# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the syntax-location grading cases share: a simulated answer, judge and observation.

Created: 2026-11-07
Last updated: 2026-11-08

This file contains :func:`answered`, which builds the dispatch outcome of one answer to
``134106``, :func:`observed`, which observes ``134106`` once with the dispatch and the
judge replaced, :func:`refused`, which asserts that answers fail a named check at every
judge score, and the answers and check names the cases share. It binds the builders of
``judged_answer_support.py`` to ``134106``, and re-exports :func:`fixed_judge` and
:func:`failed_gates` from there. No engine and no judge is called.

``mqc_uni_syntax_location.py`` reads it. Not collected, the filename carrying no
``mqc_`` prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` section 9.9.5.1.
"""

from typing import Any, Final

import pytest

from execution.dispatch import DispatchOutcome

from tests.cases import judged_answer_support
from tests.cases.judged_answer_support import SCORES, failed_gates, fixed_judge

__all__ = [
    "ERROR_CHECK", "LINE_CHECKS", "LIST_CHECK", "PAIR", "RIGHT", "RULE", "SCORES", "TASK",
    "WRONG_CAUSE", "answered", "failed_gates", "fixed_judge", "observed", "refused",
]

TASK: Final[str] = "MQC_TASK_cod_syntax_location"
RULE: Final[str] = "MQC_RULE_cod_syntax_location"
PAIR: Final[tuple[str, str]] = (TASK, RULE)
LIST_CHECK: Final[frozenset[str]] = frozenset({"ANSWER_LIST"})
ERROR_CHECK: Final[frozenset[str]] = frozenset({"A_COD_ITEM_ONE_SYNTAX_ERROR"})
LINE_CHECKS: Final[frozenset[str]] = frozenset(
    {"A_COD_ITEM_TWO_IS_LINE_TWO", "A_COD_ITEM_TWO_NO_OTHER_LINE"}
)
RIGHT: Final[str] = (
    "1. SyntaxError.\n2. Line 2.\n"
    "3. The call to sorted is never closed: its closing parenthesis is missing."
)
WRONG_CAUSE: Final[str] = (
    "1. SyntaxError.\n2. Line 2.\n3. A lambda cannot be passed as the key argument."
)


def answered(text: str) -> DispatchOutcome:
    """Build the dispatch outcome of one answer to ``134106``.

    Args:
        text (str): What the engine answered, empty for no answer.

    Returns:
        DispatchOutcome: A replayed outcome carrying the answer.
    """
    return judged_answer_support.answered(f"{TASK}::{RULE}", text)


def observed(
    monkeypatch: pytest.MonkeyPatch, outcome: DispatchOutcome, score: int = 5
) -> tuple[Any, list[Any]]:
    """Observe ``134106`` once, answered by one outcome and judged at one score.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        outcome (DispatchOutcome): What the dispatch returns.
        score (int): What the judge awards every criterion.

    Returns:
        tuple[Any, list[Any]]: The evaluation result, and the judge requests sent.
    """
    seen: list[Any] = []
    result = judged_answer_support.observe_answer(
        monkeypatch, PAIR, outcome, fixed_judge(seen, score)
    )
    return result, seen


def refused(
    monkeypatch: pytest.MonkeyPatch, answers: tuple[str, ...], expected: frozenset[str]
) -> None:
    """Observe each answer at every judge score and assert it fails one of the expected checks.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        answers (tuple[str, ...]): The answers, each observed once per score.
        expected (frozenset[str]): The checks, one of which must be among those failed.

    Returns:
        None
    """
    judged_answer_support.refused(
        lambda answer, score: observed(monkeypatch, answered(answer), score)[0],
        answers, expected,
    )
