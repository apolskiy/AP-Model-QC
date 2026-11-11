# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code that sends a family's rubric exemplars to the judge and reports the misplaced ones.

Created: 2026-11-10
Last updated: 2026-11-11

This file contains ``family_rubric_cases``, which returns the shipped cases of
one family whose rule carries a rubric; ``calibrate_family``, which sends each
of their exemplars through the harness ``calibrate``; ``calibration_failures``,
which lists every exemplar scored more than one level from the level it was
written for; ``calibration_plan`` and ``calibration_channel``, the live judge
channel calibration uses; ``rest_on_family_calibration``, which makes each
collected judged case depend on its family's collected calibration case;
``calibrate_family_live``, which joins the channel to a family; and
``assert_calibrated``, which each case in ``mqc_cal_calibration.py`` calls with
its family.

**Calibration runs in rung 2 only**, where the marker expression names
``calibration`` under a live judge, and the harness deselects it everywhere
else. A failure means the judge no longer means what the anchors say, so its
family's judged scores are uninterpretable: it exits 3 and skips them.

**The channel neither records nor reuses a judgement.** Its plan names live
mode and no fixture root, so ``--fill-gaps`` has nothing to read and nothing is
written, and its budget is the run's session, so every call counts against
``--max-spend``. Specified by ``docs/design/consumer_ci.md`` sections 7.4.1 to
7.4.3.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Final

import pytest

from cmn.calibration_runs import rest_judged_cases_on_calibration
from cmn.config import packaged_roster_path
from evaluation.calibration import CalibrationResult, calibrate, uncalibrated_message
from execution.judge_channel import JudgementPlan, judge_channel_from_roster

from tests.cases import suite_support
from tests.cases.graded_support import run_session, shipped_cases, task_material

# A HARNESS EVENT ON THE JUDGE PATH, which the channel raises led by its code.
# It is a skip with that code, never a finding about the judge.
_HARNESS_EVENT: Final[str] = "QC_HARNESS_"

# THE MARKER A CALIBRATION CASE CARRIES, which says whether a run collected one.
_CALIBRATION_MARKER: Final[str] = "calibration"


@dataclass(frozen=True)
class CalibratedExemplar:
    """One exemplar's calibration, with the case whose rubric carries it.

    Attributes:
        case_id (str): The shipped case, ``<task_id>::<rule_id>``.
        result (CalibrationResult): The harness comparison for the exemplar.
    """

    case_id: str
    result: CalibrationResult


def family_rubric_cases(family: str) -> list[Any]:
    """Return the shipped cases whose rule's first family is this one and which carry a rubric.

    Args:
        family (str): The evaluation family.

    Returns:
        list[Any]: Each :class:`EvaluationCase`, in case identifier order.
    """
    return [
        case for _, case in sorted(shipped_cases().items())
        if case.golden_rules.families
        and case.golden_rules.families[0] == family
        and case.golden_rules.rubric is not None
    ]


def calibrate_family(
    family: str, invoke: Callable[[Any], Any], *, judge_engine: str = ""
) -> list[CalibratedExemplar]:
    """Send every exemplar of the family's rubrics to the judge and compare each score.

    Each case's exemplars travel with its task's material, so the judge sees
    what it sees when grading that case.

    Args:
        family (str): The evaluation family.
        invoke (Callable): The judge, taking a composed request.
        judge_engine (str): The judge's name, recorded on each judgement.

    Returns:
        list[CalibratedExemplar]: One per exemplar sent, empty where the family's
        rules carry none.

    Raises:
        pytest.skip.Exception: Naming the code, where the judge raised a
            harness event such as a rate limit or a stopped channel.
    """
    calibrated: list[CalibratedExemplar] = []
    for case in family_rubric_cases(family):
        try:
            results = calibrate(
                case.case_id,
                case.golden_rules.rubric,
                task_material(case.task, ""),
                invoke,
                judge_engine=judge_engine,
            )
        except ValueError as error:
            if str(error).startswith(_HARNESS_EVENT):
                pytest.skip(f"{error}; calibration of {family} stopped at {case.case_id}")
            raise
        calibrated.extend(CalibratedExemplar(case.case_id, result) for result in results)
    return calibrated


def calibration_failures(calibrated: list[CalibratedExemplar]) -> list[str]:
    """Return one line per exemplar scored outside tolerance, or one where nothing was sent.

    Args:
        calibrated (list[CalibratedExemplar]): What ``calibrate_family`` returned.

    Returns:
        list[str]: ``<case> <criterion> level <n> scored <score>`` per failure.
    """
    if not calibrated:
        return ["the family sent no exemplar, so the judge was not calibrated"]
    return [
        f"{entry.case_id} {entry.result.criterion_id} "
        f"level {entry.result.intended_level} scored {entry.result.observed_score:g}"
        for entry in calibrated
        if not entry.result.passed
    ]


def calibration_plan(budget: Any = None) -> JudgementPlan:
    """Return the plan a calibration channel is built from: live, with no fixture root.

    Args:
        budget (Any): The run's dispatch session, which every judge call is
            counted against (``consumer_ci.md`` section 7.4.3), or None.

    Returns:
        JudgementPlan: Live mode, recording nothing and replaying nothing.
    """
    return JudgementPlan(mode="live", budget=budget)


def rest_on_family_calibration(items: list[Any], root: Path) -> int:
    """Make each collected judged case depend on its family's collected calibration case.

    Returns at once where no calibration case was collected, which is every
    gate and rungs 1 and 3, so those neither parse the suite nor gain a
    dependency. Otherwise hands the items and
    ``suite_support.judged_case_families`` to the harness
    ``rest_judged_cases_on_calibration``. Design: ``consumer_ci.md`` section
    7.4.2.

    Args:
        items (list): The collected items, after every selector.
        root (Path): This repository's root.

    Returns:
        int: The number of cases given a dependency.
    """
    if not any(item.get_closest_marker(_CALIBRATION_MARKER) for item in items):
        return 0
    return rest_judged_cases_on_calibration(
        items, suite_support.judged_case_families(root)
    )


@lru_cache(maxsize=4)
def calibration_channel(
    judge_engine: str, keep_connection: bool, engine: str = "", ceiling: float = 0.0
) -> Any:
    """Return the run's calibration channel, built once per judge and ceiling.

    Cached because pacing is per channel, as ``graded_support._channel`` is.
    Its plan's budget is the run's session for the candidate engine and the
    ceiling, so its judge calls count against ``--max-spend``.

    Args:
        judge_engine (str): The judge engine, empty for the roster's.
        keep_connection (bool): Whether to hold the connection between judgements.
        engine (str): The candidate engine, ``--engine``, which keys the session.
        ceiling (float): ``--max-spend``, zero for none.

    Returns:
        Any: The :class:`JudgeChannel`.
    """
    return judge_channel_from_roster(
        packaged_roster_path(),
        judge_engine or None,
        keep_connection=keep_connection,
        plan=calibration_plan(run_session(engine, ceiling)),
    )


def assert_calibrated(config: Any, family: str) -> None:
    """Calibrate one family against the run's judge, failing on each exemplar out of tolerance.

    The failure is the harness ``uncalibrated_message``, led by
    ``QC_HARNESS_JUDGE_UNCALIBRATED`` and naming each misplaced exemplar.

    Args:
        config (Any): pytest's configuration.
        family (str): The evaluation family.

    Returns:
        None
    """
    failures = calibration_failures(calibrate_family_live(config, family))
    assert not failures, uncalibrated_message(family, failures)


def calibrate_family_live(config: Any, family: str) -> list[CalibratedExemplar]:
    """Calibrate one family against the judge this run names.

    Args:
        config (Any): pytest's configuration.
        family (str): The evaluation family.

    Returns:
        list[CalibratedExemplar]: As ``calibrate_family`` returns.
    """
    channel = calibration_channel(
        str(config.getoption("--judge-engine") or ""),
        bool(config.getoption("--keep-connection")),
        str(config.getoption("--engine") or ""),
        float(config.getoption("--max-spend") or 0.0),
    )
    return calibrate_family(family, channel.invoke, judge_engine=channel.engine)
