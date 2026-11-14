# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code that evaluates a family's calibration samples and reports those that disagreed.

Created: 2026-11-10
Last updated: 2026-11-12

This file contains ``calibration_samples`` and ``every_calibration_sample``,
which read the authored samples in ``data/calibration/``; ``sample_case``, the
shipped case a sample answers; ``calibrate_family``, which evaluates each of a
family's samples through the harness ``calibrate_sample``;
``calibration_failures``, which lists every sample that disagreed;
``checks_disagreements``, our checks' half of every sample with the judge
withheld; ``sample_integrity_problems``, every sample that does not answer a
shipped case of its family; ``calibration_plan`` and ``calibration_channel``,
the live judge channel calibration uses; ``rest_on_family_calibration``, which
makes each judged case depend on its family's calibration, collected or carried
from a record; ``samples_digest``, the digest a record is valid against;
``adopt_record`` and ``publish_record``, which read and write the record;
``calibrate_family_live``, which joins the channel to a family; and
``assert_calibrated``, which each case in ``mqc_cal_calibration.py`` calls with
its family.

**Calibration runs in each judge's calibration workflow only**, where the
marker expression names ``calibration`` under a live judge, and the harness
deselects it everywhere else. That session writes a record each live band reads
(``consumer_ci.md`` section 7.4.5). A failure means the judge missed a stated
mistake or marked down a clean sample, so its family's judged scores are
uninterpretable: it exits 3, and every band reading the record skips them.

**The channel neither records nor reuses a judgement.** Its plan names live
mode and no fixture root, so ``--fill-gaps`` has nothing to read and nothing is
written, and its budget is the run's session, so every call counts against
``--max-spend``. Specified by ``docs/design/consumer_ci.md`` sections 7.4.1 to
7.4.3.
"""

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Optional

import pytest
import yaml

from cmn.calibration_record import adopt_calibration_record, publish_calibration_record
from cmn.calibration_runs import rest_judged_cases_on_calibration
from cmn.config import packaged_roster_path
from evaluation.calibration import (
    CalibrationOutcome,
    CalibrationSample,
    calibrate_sample,
    calibration_context,
    deterministic_disagreement,
    uncalibrated_message,
)
from evaluation.judge import JudgeBinding
from evaluation.pipeline import evaluate_observation
from execution.judge_channel import JudgementPlan, judge_channel_from_roster
from execution.preflight import served_facts

from tests.cases import suite_support
from tests.cases.graded_support import repository_root, run_session, shipped_cases

# A HARNESS EVENT ON THE JUDGE PATH, which the channel raises led by its code.
# It is a skip with that code, never a finding about the judge.
_HARNESS_EVENT: Final[str] = "QC_HARNESS_"

# THE MARKER A CALIBRATION CASE CARRIES, which says whether a run collected one.
_CALIBRATION_MARKER: Final[str] = "calibration"

# WHERE THE SAMPLES LIVE, one file per family, beside the corpus and outside
# the `tasks` and `rules` directories the harness loads.
_SAMPLES: Final[str] = "data/calibration"


def _sample_root() -> Path:
    """Return the directory holding one sample file per calibrated family.

    Returns:
        Path: ``data/calibration`` under this repository's root.
    """
    return repository_root() / _SAMPLES


def calibration_samples(family: str) -> list[CalibrationSample]:
    """Return the family's calibration samples, in file order.

    Args:
        family (str): The evaluation family, which names its file.

    Returns:
        list[CalibrationSample]: One per authored sample, empty where the
        family has no file or the file holds none.
    """
    source = _sample_root() / f"{family}.yaml"
    if not source.is_file():
        return []
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    return [CalibrationSample.from_dict(entry) for entry in payload.get("samples") or []]


def every_calibration_sample() -> dict[str, list[CalibrationSample]]:
    """Return every family's calibration samples, by the family its file names.

    Returns:
        dict[str, list[CalibrationSample]]: Family to its samples, in family order.
    """
    return {
        source.stem: calibration_samples(source.stem)
        for source in sorted(_sample_root().glob("*.yaml"))
    }


def sample_case(sample: CalibrationSample) -> Any:
    """Return the shipped case a sample answers.

    Args:
        sample (CalibrationSample): The sample.

    Returns:
        Any: The :class:`EvaluationCase`.

    Raises:
        KeyError: Naming the sample, where no shipped case carries its task
            and rule.
    """
    case = shipped_cases().get(sample.case_id)
    if case is None:
        raise KeyError(f"calibration sample {sample.sample_id} answers no shipped case")
    return case


def calibrate_family(family: str, binding: JudgeBinding) -> list[CalibrationOutcome]:
    """Evaluate every calibration sample of a family through the graded path.

    Args:
        family (str): The evaluation family.
        binding (JudgeBinding): The judge being calibrated.

    Returns:
        list[CalibrationOutcome]: One per sample, empty where the family has none.

    Raises:
        pytest.skip.Exception: Naming the code, where the judge raised a
            harness event such as a rate limit or a stopped channel.
    """
    outcomes: list[CalibrationOutcome] = []
    for sample in calibration_samples(family):
        try:
            outcomes.append(calibrate_sample(sample_case(sample), sample, binding))
        except ValueError as error:
            if str(error).startswith(_HARNESS_EVENT):
                pytest.skip(f"{error}; calibration of {family} stopped at {sample.sample_id}")
            raise
    return outcomes


def calibration_failures(outcomes: list[CalibrationOutcome]) -> list[str]:
    """Return one line per sample that disagreed, or one where nothing was evaluated.

    Args:
        outcomes (list[CalibrationOutcome]): What ``calibrate_family`` returned.

    Returns:
        list[str]: The harness's disagreement per sample, naming its mistake
        and every criterion's score.
    """
    if not outcomes:
        return ["the family holds no calibration sample, so the judge was not calibrated"]
    return [outcome.disagreement for outcome in outcomes if not outcome.agreed]


def checks_disagreements() -> list[str]:
    """Return every sample our checks disagree with, evaluated with the judge withheld.

    Design: ``consumer_ci.md`` section 7.4.1.1. The withheld binding asks no
    judge, so this costs nothing and runs in the unit gate.

    Returns:
        list[str]: The harness's deterministic disagreement per sample, empty
        where every sample agrees.
    """
    withheld = JudgeBinding(candidate_engine="calibration", withheld=True)
    found: list[str] = []
    for samples in every_calibration_sample().values():
        for sample in samples:
            case = sample_case(sample)
            result = evaluate_observation(
                calibration_context(case, sample), withheld, judge_on_failure=True
            )
            disagreement = deterministic_disagreement(sample, case, result)
            if disagreement:
                found.append(disagreement)
    return found


def sample_integrity_problems() -> list[str]:
    """Return every sample that does not answer a shipped case of its family as declared.

    Design: ``consumer_ci.md`` section 7.4.1.1. A sample answers a shipped
    case whose rule's first family is its file's and which is not declared
    adversarial, names only that case's constraints or its rule's check
    identifiers, and carries an identifier no other sample does; each family
    holds a clean and a flawed sample.

    Returns:
        list[str]: One line per problem, empty where every sample holds.
    """
    problems: list[str] = []
    seen: set[str] = set()
    for family, samples in every_calibration_sample().items():
        if not any(sample.flawed for sample in samples) or all(
            sample.flawed for sample in samples
        ):
            problems.append(f"{family} does not hold both a clean and a flawed sample")
        for sample in samples:
            if sample.sample_id in seen:
                problems.append(f"{sample.sample_id} is carried by two samples")
            seen.add(sample.sample_id)
            case = shipped_cases().get(sample.case_id)
            if case is None:
                problems.append(f"{sample.sample_id} answers no shipped case")
                continue
            problems.extend(_case_problems(family, sample, case))
    return problems


def _case_problems(family: str, sample: CalibrationSample, case: Any) -> list[str]:
    """Return what is wrong with a sample against the case it answers.

    Args:
        family (str): The family its file names.
        sample (CalibrationSample): The sample.
        case (Any): The shipped case it answers.

    Returns:
        list[str]: One line per problem.
    """
    problems: list[str] = []
    rules = case.golden_rules
    if not rules.families or rules.families[0] != family:
        problems.append(f"{sample.sample_id} answers a case of {list(rules.families)}")
    if case.task.contains_adversarial_content:
        problems.append(f"{sample.sample_id} answers a declared adversarial case")
    readable = {constraint.constraint_id for constraint in case.task.constraints}
    readable |= {assertion.assertion_id for assertion in rules.assertions}
    unknown = [entry for entry in sample.violates if entry not in readable]
    if unknown:
        problems.append(f"{sample.sample_id} names {unknown}, which its case does not carry")
    return problems


def calibration_plan(budget: Any = None) -> JudgementPlan:
    """Return the plan a calibration channel is built from: live, with no fixture root.

    Args:
        budget (Any): The run's dispatch session, which every judge call is
            counted against (``consumer_ci.md`` section 7.4.3), or None.

    Returns:
        JudgementPlan: Live mode, recording nothing and replaying nothing.
    """
    return JudgementPlan(mode="live", budget=budget)


def rest_on_family_calibration(items: list[Any], root: Path, config: Any = None) -> int:
    """Make each judged case depend on its family's calibration, collected or recorded.

    Returns at once where the session neither collected a calibration case nor
    names ``--calibration-record``, which is every gate and rung 1, so those
    neither parse the suite nor gain a dependency. Otherwise hands the items
    and ``suite_support.judged_case_families`` to the harness
    ``rest_judged_cases_on_calibration``, which wires each judged case to the
    calibration collected beside it or carried from the record. Design:
    ``consumer_ci.md`` sections 7.4.2 and 7.4.5.

    Args:
        items (list): The collected items, after every selector.
        root (Path): This repository's root.
        config (Any): pytest's configuration, read for ``--calibration-record``;
            None where the caller has none.

    Returns:
        int: The number of cases given a dependency.
    """
    named = bool(config is not None and config.getoption("--calibration-record", None))
    if not named and not any(item.get_closest_marker(_CALIBRATION_MARKER) for item in items):
        return 0
    return rest_judged_cases_on_calibration(
        items, suite_support.judged_case_families(root)
    )


def samples_digest(sample_root: Optional[Path] = None) -> str:
    """Return the digest a calibration record is valid against.

    Every ``*.yaml`` under the root, in name order, is hashed by its name and
    its content with CRLF read as LF, so an edited, added, removed or renamed
    sample moves the digest and a checkout on either platform computes the
    same one. Design: ``consumer_ci.md`` section 7.4.5.

    Args:
        sample_root (Optional[Path]): The samples directory, ``data/calibration``
            where None.

    Returns:
        str: The first sixteen hexadecimal digits of the SHA-256.
    """
    digest = hashlib.sha256()
    for source in sorted((sample_root or _sample_root()).glob("*.yaml")):
        digest.update(source.name.encode("utf-8") + b"\0")
        digest.update(source.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()[:16]


def adopt_record(config: Any) -> Optional[str]:
    """Adopt the calibration record a band session names, at session start.

    Hands the samples digest and the served-identity reader to the harness
    ``adopt_calibration_record``, which reads the record only where the
    session names one under a live judge. Design: ``consumer_ci.md`` section
    7.4.5.

    Args:
        config (Any): pytest's configuration.

    Returns:
        Optional[str]: Why the record is invalid, or None.
    """
    if not config.getoption("--calibration-record", None):
        return None
    return adopt_calibration_record(config, samples_digest(), served_reader=served_facts)


def publish_record(config: Any, root: Path) -> Optional[Path]:
    """Write the calibration record a calibration session names, at session end.

    Design: ``consumer_ci.md`` section 7.4.5.

    Args:
        config (Any): pytest's configuration.
        root (Path): This repository's root.

    Returns:
        Optional[Path]: The record written, None where none was.
    """
    if not config.getoption("--record-calibration", None):
        return None
    return publish_calibration_record(
        config, samples_digest(), suite_support.judged_case_families(root),
        served_reader=served_facts,
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
    """Calibrate one family against the run's judge, failing on each sample that disagreed.

    The failure is the harness ``uncalibrated_message``, led by
    ``QC_HARNESS_JUDGE_UNCALIBRATED`` and naming each sample that disagreed.

    Args:
        config (Any): pytest's configuration.
        family (str): The evaluation family.

    Returns:
        None
    """
    failures = calibration_failures(calibrate_family_live(config, family))
    assert not failures, uncalibrated_message(family, failures)


def calibrate_family_live(config: Any, family: str) -> list[CalibrationOutcome]:
    """Calibrate one family against the judge this run names.

    Args:
        config (Any): pytest's configuration.
        family (str): The evaluation family.

    Returns:
        list[CalibrationOutcome]: As ``calibrate_family`` returns.
    """
    engine = str(config.getoption("--engine") or "")
    channel = calibration_channel(
        str(config.getoption("--judge-engine") or ""),
        bool(config.getoption("--keep-connection")),
        engine,
        float(config.getoption("--max-spend") or 0.0),
    )
    binding = JudgeBinding(
        invoke=channel.invoke, judge_engine=channel.engine, candidate_engine=engine
    )
    return calibrate_family(family, binding)
