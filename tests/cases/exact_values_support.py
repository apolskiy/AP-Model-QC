# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the exact-values grading cases share: a simulated answer, judge and observation.

Created: 2026-11-08
Last updated: 2026-11-08

This file contains :func:`answered`, which builds the dispatch outcome of one answer to
``134201``, :func:`observed`, which observes ``134201`` once with the dispatch replaced
and the judge awarding a fixed score or one score per criterion, :func:`refused`, which
asserts that answers fail a named check at every judge score, and the answers, check
names and criterion names the cases share. It binds the builders of
``judged_answer_support.py`` to ``134201``. No engine and no judge is called.

``mqc_uni_exact_values.py`` reads it. Not collected, the filename carrying no ``mqc_``
prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` section 9.4.3.
"""

from typing import Any, Final, Optional

import pytest

from execution.dispatch import DispatchOutcome

from tests.cases import judged_answer_support
from tests.cases.judged_answer_support import criterion_judge

TASK: Final[str] = "MQC_TASK_gnd_exact_values"
RULE: Final[str] = "MQC_RULE_gnd_exact_values"
PAIR: Final[tuple[str, str]] = (TASK, RULE)
CASE_ID: Final[str] = f"{TASK}::{RULE}"

# THE DICTIONARY THE PAIR CHECKS HOLD, each region with its figure.
PAIR_CHECKS: Final[frozenset[str]] = frozenset({
    "A_GND_PAIR_NORTH_AMERICA", "A_GND_PAIR_EMEA", "A_GND_PAIR_JAPAN", "A_GND_PAIR_AUSTRALIA",
})
TOTAL_CHECK: Final[frozenset[str]] = frozenset({"A_GND_FIGURE_TOTAL"})
SENTENCE_CHECK: Final[frozenset[str]] = frozenset({"A_GND_THREE_SENTENCES"})
REGION_CHECK: Final[frozenset[str]] = frozenset({"A_GND_REGION_IN_EVERY_SENTENCE"})
TWO_CHECK: Final[frozenset[str]] = frozenset({"A_GND_AT_MOST_TWO_REGIONS"})
EVERY_CHECK: Final[frozenset[str]] = (
    PAIR_CHECKS | TOTAL_CHECK | SENTENCE_CHECK | REGION_CHECK | TWO_CHECK
)
SUMMARY: Final[str] = "C_GND_SUMMARY_READS"

# North America with EMEA, Japan alone, Australia alone, the total beside a region.
RIGHT: Final[str] = (
    "North America led Q3 with 41.2 million, ahead of EMEA at 28.7 million. Japan added "
    "11.4 million, the third largest region. Australia contributed 6.1 million, bringing "
    "the four-region total to 87.4 million."
)
# North America named twice beside EMEA, and Japan with Australia: two regions each.
PAIRED: Final[str] = (
    "North America led Q3 with 41.2 million, ahead of EMEA at 28.7 million, which trailed "
    "North America by 12.5 million. Japan added 11.4 million and Australia 6.1 million. "
    "Australia's figure brought the four-region total to 87.4 million."
)


def answered(text: str) -> DispatchOutcome:
    """Build the dispatch outcome of one answer to ``134201``.

    Args:
        text (str): What the engine answered, empty for no answer.

    Returns:
        DispatchOutcome: A replayed outcome carrying the answer.
    """
    return judged_answer_support.answered(CASE_ID, text)


def observed(
    monkeypatch: pytest.MonkeyPatch, outcome: DispatchOutcome, score: int = 5,
    scores: Optional[dict[str, int]] = None,
) -> tuple[Any, list[Any]]:
    """Observe ``134201`` once, answered by one outcome and judged at one score or per criterion.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        outcome (DispatchOutcome): What the dispatch returns.
        score (int): What the judge awards a criterion ``scores`` does not name.
        scores (Optional[dict[str, int]]): Criterion identifier to its score.

    Returns:
        tuple[Any, list[Any]]: The evaluation result, and the judge requests sent.
    """
    seen: list[Any] = []
    result = judged_answer_support.observe_answer(
        monkeypatch, PAIR, outcome, criterion_judge(seen, scores or {}, score)
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
