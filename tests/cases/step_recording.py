# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code that records a graded case's steps into Allure and the log.

Created: 2026-10-16
Last updated: 2026-10-21

This file contains ``record_observation_step``, which writes the step one observation
is, with its pipeline phases nested beneath it, and ``record_remaining_steps``, which
writes the steps after the observations, the escalation not taken and then the
comparison.

**``graded_support`` calls both** as each graded case is observed, so every case's
Allure report and log carry one step per dispatch, then the escalation steps not taken,
then the comparison. ``mqc_uni_instrument_audit.py`` asserts the calls are made. The
harness computes every step (``cmn.steps``); this module writes them and decides
nothing.

Design: ``consumer_ci.md`` section 9.4.3.3, implementing harness
``harness_test_taxonomy.md`` section 8.2.2.
"""

import logging
from typing import Any, Sequence

import allure

from cmn.steps import CaseStep, StepOutcome, case_steps, observation_step, step_lines

logger = logging.getLogger(__name__)


def record_observation_step(
    case_id: str, number: int, outcome: Any, result: Any
) -> CaseStep:
    """Record the step one observation is, with its phases beneath.

    Args:
        case_id (str): Which case.
        number (int): The step number, the observation index plus one.
        outcome (Any): The dispatch outcome, or None.
        result (Any): The evaluation result, or None where evaluation never ran.

    Returns:
        CaseStep: The step recorded.
    """
    step = observation_step(number, outcome, result)
    _record(case_id, [step])
    return step


def record_remaining_steps(
    case_id: str, results: Sequence[Any], *, configured: int
) -> list[CaseStep]:
    """Record the steps after the observations: escalation not taken, then the comparison.

    Args:
        case_id (str): Which case.
        results (Sequence): Every observation's evaluation result, in order,
            each already recorded as its own step by ``observe``.
        configured (int): How many observations the run takes before
            escalating.

    Returns:
        list[CaseStep]: The steps recorded, numbered after the observations.
    """
    steps = case_steps([(None, result) for result in results], configured=configured)
    remaining = steps[len(results):]
    _record(case_id, remaining)
    return remaining


def _record(case_id: str, steps: Sequence[CaseStep]) -> None:
    """Write steps into Allure, each half holding its phases, and into the log.

    Args:
        case_id (str): Which case.
        steps (Sequence): The steps.

    Returns:
        None
    """
    for step in steps:
        for half, phases in (
            (step.action, step.action_phases),
            (step.verification, step.verification_phases),
        ):
            with allure.step(f"{half.label} [{half.outcome}]"):
                for phase in phases:
                    _record_phase(phase)
    for line in step_lines(case_id, steps):
        logger.info("%s", line)


def _record_phase(phase: StepOutcome) -> None:
    """Write one pipeline phase as a nested Allure step.

    Args:
        phase (StepOutcome): The phase.

    Returns:
        None
    """
    with allure.step(f"{phase.label} [{phase.outcome}]"):
        if phase.detail:
            allure.attach(
                phase.detail,
                name=f"{phase.label} detail",
                attachment_type=allure.attachment_type.TEXT,
            )
