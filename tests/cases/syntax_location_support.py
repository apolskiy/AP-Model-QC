# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the syntax-location grading cases share: a simulated answer, judge and observation.

Created: 2026-11-07
Last updated: 2026-11-07

This file contains :func:`answered`, which builds the dispatch outcome of one answer,
:func:`fixed_judge`, a judge awarding one score to every criterion and logging each
request, :func:`observed`, which observes ``134106`` once through
``tests.cases.graded_support.observe`` with both replaced, :func:`failed_gates`, and
:func:`refused`, which asserts that answers fail a named check at every judge score; and
the answers and check names the cases share. No engine and no judge is called.

``mqc_uni_syntax_location.py`` reads it. Not collected, the filename carrying no
``mqc_`` prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` section 9.9.5.1.
"""

from typing import Any, Final

import pytest

from cmn.case_steps import step
from evaluation.judge import JudgeBinding
from execution.dispatch import DispatchOutcome
from execution.normalize import NormalizedResponse

from tests.cases import graded_support
from tests.cases.graded_support import observe
from tests.cases.instrument_support import SimulatedGradedConfig

TASK: Final[str] = "MQC_TASK_cod_syntax_location"
RULE: Final[str] = "MQC_RULE_cod_syntax_location"
LIST_CHECK: Final[frozenset[str]] = frozenset({"ANSWER_LIST"})
ERROR_CHECK: Final[frozenset[str]] = frozenset({"A_COD_ITEM_ONE_SYNTAX_ERROR"})
LINE_CHECKS: Final[frozenset[str]] = frozenset(
    {"A_COD_ITEM_TWO_IS_LINE_TWO", "A_COD_ITEM_TWO_NO_OTHER_LINE"}
)
SCORES: Final[tuple[int, ...]] = (1, 2, 3, 4, 5)
RIGHT: Final[str] = (
    "1. SyntaxError.\n2. Line 2.\n"
    "3. The call to sorted is never closed: its closing parenthesis is missing."
)
WRONG_CAUSE: Final[str] = (
    "1. SyntaxError.\n2. Line 2.\n3. A lambda cannot be passed as the key argument."
)


def answered(text: str) -> DispatchOutcome:
    """Build the dispatch outcome of one answer.

    Args:
        text (str): What the engine answered, empty for no answer.

    Returns:
        DispatchOutcome: A replayed outcome carrying the answer.
    """
    return DispatchOutcome(
        case_id=f"{TASK}::{RULE}", engine="gemini", mode="replay", duration_ms=12,
        duration_kind="measured", attempts=1, rate_limit_encounters=0,
        response=NormalizedResponse(
            case_id=f"{TASK}::{RULE}", engine="gemini", mode="replay",
            requested_model="gemini-4-argon", resolved_model="gemini-4-argon", text=text,
            output_tokens=len(text.split()), duration_ms=12, finish_reason="stop",
            raw_reference="",
        ),
    )


def fixed_judge(seen: list[Any], score: int) -> JudgeBinding:
    """Return a judge awarding one score to every criterion the request asks for.

    Args:
        seen (list[Any]): Receives every request the judge is sent.
        score (int): What every criterion is awarded.

    Returns:
        JudgeBinding: The binding.
    """

    def invoke(request: Any) -> dict[str, Any]:
        """Award every required criterion the fixed score.

        Args:
            request (Any): The composed judgement request.

        Returns:
            dict[str, Any]: One score and rationale per required criterion.
        """
        seen.append(request)
        return {
            "scores": {
                criterion_id: {"score": score, "rationale": "Simulated."}
                for criterion_id in request.reply_schema["properties"]["scores"]["required"]
            }
        }

    return JudgeBinding(invoke=invoke, judge_engine="claude", candidate_engine="gemini")


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
    monkeypatch.setattr(graded_support, "dispatch_case", lambda *args, **kwargs: outcome)
    monkeypatch.setattr(graded_support, "record_observation", lambda *args, **kwargs: None)
    monkeypatch.setattr(graded_support, "record_observation_step", lambda *args, **kwargs: None)
    result = observe(SimulatedGradedConfig("claude"), TASK, RULE, judge=fixed_judge(seen, score))
    return result, seen


def failed_gates(result: Any) -> set[str]:
    """Return the assertions that failed, the list check among them.

    Args:
        result (Any): The evaluation result.

    Returns:
        set[str]: Their identifiers.
    """
    return {entry.assertion_id for entry in result.assertion_results if not entry.passed}


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
    number = 0
    for answer in answers:
        for score in SCORES:
            number += 1
            step(number, f"observe {answer!r}, judged {score}")
            result, _ = observed(monkeypatch, answered(answer), score)
            assert not result.passed, f"{answer!r} passed although judged {score}"

            number += 1
            step(number, f"read which checks {answer!r} failed, judged {score}")
            failed = failed_gates(result)
            assert failed & expected, (
                f"{answer!r} failed {failed or 'no check'}, none of {sorted(expected)}"
            )
