# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the rubric anchor cases share: the floor case's criterion and its judge prompt.

Created: 2026-11-05
Last updated: 2026-11-05

This file contains :func:`floor_rubric`, which returns the floor case and the
one criterion its judge scores, and :func:`judge_prompt`, which returns the
prompt the judge is sent for an answer, composed as the pipeline composes it
and with no judge called.

``mqc_uni_rubric_anchors.py`` reads it. Not collected, the filename carrying no
``mqc_`` prefix.

Specified by ``docs/testing/model_evaluation_test_plan.md`` section 9.13.1.
"""

from typing import Any, Final

from evaluation.pipeline import ObservationContext, observation_judge_request

from tests.cases.graded_support import case_for, task_material

_TASK: Final[str] = "MQC_TASK_prm_floor_short"
_RULE: Final[str] = "MQC_RULE_prm_floor_short"


def floor_rubric() -> tuple[Any, Any]:
    """Return the floor case and its one criterion.

    Returns:
        tuple: The case, and the rubric criterion its judge scores.
    """
    case = case_for(_TASK, _RULE)
    return case, case.golden_rules.rubric.criteria[0]


def judge_prompt(case: Any, answer: str) -> str:
    """Return the prompt the judge is sent for an answer, as the pipeline composes it.

    Args:
        case (Any): The case being judged.
        answer (str): The response being judged.

    Returns:
        str: The rendered judge prompt.
    """
    return observation_judge_request(ObservationContext(
        case_id=case.case_id,
        rules=case.golden_rules,
        material=task_material(case.task, answer),
        declared_adversarial=case.task.contains_adversarial_content,
        observation_index=0,
    )).rendered()
