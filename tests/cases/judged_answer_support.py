# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the simulated grading cases share: an answer, a judge, an observation and its checks.

Created: 2026-11-08
Last updated: 2026-11-08

This file contains :func:`answered`, which builds the dispatch outcome of one answer;
:func:`fixed_judge` and :func:`criterion_judge`, judges awarding a fixed score to every
criterion or one score per criterion and logging each request; :func:`observe_answer`,
which observes one task and rule pair through ``tests.cases.graded_support.observe``
with the dispatch and the judge replaced; :func:`failed_gates`; and the steps the cases
share: :func:`unanswered_fails_unjudged`, :func:`dispatch_error_is_skipped`,
:func:`accepted`, which asserts that answers meet every check and pass, and
:func:`refused`, which asserts that answers fail a named check at every judge score.
No engine and no judge is called.

``syntax_location_support.py`` and ``exact_values_support.py`` read it. Not collected,
the filename carrying no ``mqc_`` prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` sections 9.4.3 and 9.9.5.1.
"""

from typing import Any, Callable, Final, Optional

import pytest

from cmn.case_steps import step
from evaluation.judge import JudgeBinding
from execution.dispatch import DispatchOutcome
from execution.normalize import NormalizedResponse

from tests.cases import graded_support
from tests.cases.graded_support import observe
from tests.cases.instrument_support import SimulatedGradedConfig

SCORES: Final[tuple[int, ...]] = (1, 2, 3, 4, 5)
_UNAVAILABLE: Final[str] = "QC_HARNESS_PROVIDER_UNAVAILABLE"


def answered(case_id: str, text: str) -> DispatchOutcome:
    """Build the dispatch outcome of one answer.

    Args:
        case_id (str): The task and rule pair, joined by ``::``.
        text (str): What the engine answered, empty for no answer.

    Returns:
        DispatchOutcome: A replayed outcome carrying the answer.
    """
    return DispatchOutcome(
        case_id=case_id, engine="gemini", mode="replay", duration_ms=12,
        duration_kind="measured", attempts=1, rate_limit_encounters=0,
        response=NormalizedResponse(
            case_id=case_id, engine="gemini", mode="replay",
            requested_model="gemini-4-argon", resolved_model="gemini-4-argon", text=text,
            output_tokens=len(text.split()), duration_ms=12, finish_reason="stop",
            raw_reference="",
        ),
    )


def criterion_judge(seen: list[Any], scores: dict[str, int], default: int = 5) -> JudgeBinding:
    """Return a judge awarding each criterion its own score.

    Args:
        seen (list[Any]): Receives every request the judge is sent.
        scores (dict[str, int]): Criterion identifier to the score it is awarded.
        default (int): What a criterion not named in ``scores`` is awarded.

    Returns:
        JudgeBinding: The binding.
    """

    def invoke(request: Any) -> dict[str, Any]:
        """Award every required criterion its score.

        Args:
            request (Any): The composed judgement request.

        Returns:
            dict[str, Any]: One score and rationale per required criterion.
        """
        seen.append(request)
        return {
            "scores": {
                criterion_id: {"score": scores.get(criterion_id, default),
                               "rationale": "Simulated."}
                for criterion_id in request.reply_schema["properties"]["scores"]["required"]
            }
        }

    return JudgeBinding(invoke=invoke, judge_engine="claude", candidate_engine="gemini")


def fixed_judge(seen: list[Any], score: int) -> JudgeBinding:
    """Return a judge awarding one score to every criterion the request asks for.

    Args:
        seen (list[Any]): Receives every request the judge is sent.
        score (int): What every criterion is awarded.

    Returns:
        JudgeBinding: The binding.
    """
    return criterion_judge(seen, {}, score)


def observe_answer(
    monkeypatch: pytest.MonkeyPatch, pair: tuple[str, str], outcome: DispatchOutcome,
    judge: JudgeBinding,
) -> Any:
    """Observe one task and rule pair once, answered by one outcome and judged by one judge.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        pair (tuple[str, str]): The task and the rule.
        outcome (DispatchOutcome): What the dispatch returns.
        judge (JudgeBinding): The judge.

    Returns:
        Any: The evaluation result.
    """
    monkeypatch.setattr(graded_support, "dispatch_case", lambda *args, **kwargs: outcome)
    monkeypatch.setattr(graded_support, "record_observation", lambda *args, **kwargs: None)
    monkeypatch.setattr(graded_support, "record_observation_step", lambda *args, **kwargs: None)
    return observe(SimulatedGradedConfig("claude"), pair[0], pair[1], judge=judge)


def failed_gates(result: Any) -> set[str]:
    """Return the assertions that failed, the list check among them.

    Args:
        result (Any): The evaluation result.

    Returns:
        set[str]: Their identifiers.
    """
    return {entry.assertion_id for entry in result.assertion_results if not entry.passed}


def unanswered_fails_unjudged(
    observe_one: Callable[[DispatchOutcome], tuple[Any, list[Any]]], case_id: str
) -> None:
    """Assert that an answer carrying no text fails with ``QC_LLM_NO_OUTPUT``, unjudged.

    Args:
        observe_one (Callable): Observes one outcome, returning the result and the
            judge requests sent.
        case_id (str): The task and rule pair, joined by ``::``.

    Returns:
        None
    """
    step(1, "observe an answer carrying no text")
    result, seen = observe_one(answered(case_id, ""))
    assert not result.passed, "an answer never given passed"

    step(2, "read the code it carried")
    assert "QC_LLM_NO_OUTPUT" in result.taxonomy_codes, (
        f"an answer never given carried {result.taxonomy_codes}, not QC_LLM_NO_OUTPUT"
    )

    step(3, "read whether any assertion ran")
    assert not result.assertion_results, "assertions ran against an answer never given"

    step(4, "read whether the judge was asked")
    assert not seen, "the judge was asked to score an answer never given"


def dispatch_error_is_skipped(monkeypatch: pytest.MonkeyPatch, pair: tuple[str, str]) -> None:
    """Assert that a dispatch returning an error skips with its harness code, unevaluated.

    Args:
        monkeypatch (pytest.MonkeyPatch): pytest's patcher.
        pair (tuple[str, str]): The task and the rule.

    Returns:
        None
    """
    recorded: list[Any] = []
    evaluated: list[Any] = []
    monkeypatch.setattr(
        graded_support, "evaluate_observation",
        lambda *args, **kwargs: evaluated.append(args),
    )
    outcome = DispatchOutcome(
        case_id=f"{pair[0]}::{pair[1]}", engine="gemini", mode="live", duration_ms=12,
        duration_kind="measured", attempts=3, rate_limit_encounters=0,
        taxonomy_code=_UNAVAILABLE,
    )
    monkeypatch.setattr(graded_support, "dispatch_case", lambda *args, **kwargs: outcome)
    monkeypatch.setattr(graded_support, "record_observation_step", lambda *args, **kwargs: None)
    keep = recorded.append
    monkeypatch.setattr(graded_support, "record_observation", lambda entry, *rest: keep(entry))

    step(1, "observe a dispatch the provider could not serve")
    with pytest.raises(pytest.skip.Exception, match=_UNAVAILABLE):
        observe(SimulatedGradedConfig("claude"), pair[0], pair[1], judge=fixed_judge([], 5))

    step(2, "read what was recorded")
    assert [(entry.skip_reason, entry.taxonomy_code) for entry in recorded] == [
        ("environmental", _UNAVAILABLE)
    ], f"recorded {recorded}, not one environmental skip carrying {_UNAVAILABLE}"

    step(3, "read whether anything was evaluated")
    assert not evaluated, "a dispatch error was evaluated as an answer"


def accepted(
    observe_one: Callable[[str], tuple[Any, list[Any]]], answers: tuple[str, ...]
) -> None:
    """Observe each answer judged 5 and assert it meets every check, is judged and passes.

    Args:
        observe_one (Callable): Observes one answer, returning the result and the judge
            requests sent.
        answers (tuple[str, ...]): The answers.

    Returns:
        None
    """
    number = 0
    for answer in answers:
        number += 1
        step(number, f"observe {answer!r}, judged 5")
        result, seen = observe_one(answer)
        assert not failed_gates(result), f"{answer!r} failed {failed_gates(result)}"

        number += 1
        step(number, f"read whether {answer!r} was judged")
        assert seen, f"{answer!r} was never judged"

        number += 1
        step(number, f"read whether {answer!r} passed")
        assert result.passed, f"{answer!r} failed although every check held"


def refused(
    observe_one: Callable[[str, int], Any], answers: tuple[str, ...],
    expected: frozenset[str], scores: Optional[tuple[int, ...]] = None,
) -> None:
    """Observe each answer at every judge score and assert it fails one of the expected checks.

    Args:
        observe_one (Callable): Observes one answer at one score, returning the result.
        answers (tuple[str, ...]): The answers, each observed once per score.
        expected (frozenset[str]): The checks, one of which must be among those failed.
        scores (Optional[tuple[int, ...]]): The scores, every one from 1 to 5 by default.

    Returns:
        None
    """
    number = 0
    for answer in answers:
        for score in scores or SCORES:
            number += 1
            step(number, f"observe {answer!r}, judged {score}")
            result = observe_one(answer, score)
            assert not result.passed, f"{answer!r} passed although judged {score}"

            number += 1
            step(number, f"read which checks {answer!r} failed, judged {score}")
            failed = failed_gates(result)
            assert failed & expected, (
                f"{answer!r} failed {failed or 'no check'}, none of {sorted(expected)}"
            )
