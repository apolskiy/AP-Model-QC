# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The band check, which decides from a band's JUnit XML whether that band passed.

Created: 2026-10-01
Last updated: 2026-11-26

This file contains ``assess``, which compares a lower-priority band's pass rate
against the project's pass floor, ``assess_blocking``, which requires a release
blocking band to have measured and passed every case it selected, each
reporting a band the environment's skips took below its floor as not measured,
``run_status_problem``, which says whether the status the band's run reported
leaves a rate worth reading, and ``main``, the command line they run behind.
Skips are explained by cause, each missing artifact is named by kind and path,
and no skip is excused: a quarantined case is deselected before any band runs.
A run status other than ``0`` or ``1`` still has the report assessed and
logged, and then refuses.

The band composite action runs it after each band's pytest step, with
``--blocking --engine`` for P0 and P1 and without them for the lower band, and
with ``--run-status`` in every band. Its exit status is the band job's outcome,
``0`` cleared, ``1`` failed and ``4`` refused, so it decides whether a band
reads green in the run.

**The run step reports and this tool decides**, since 2026-11-02. A composite
action step cannot carry ``continue-on-error``, so a pytest step exiting 1
failed the job before this tool was consulted, and all four engine gates went
red on a lower band that had cleared its floor.

Specified by ``docs/design/consumer_ci.md`` section 3.12.2.

**Two floors, because the bands answer different questions.** A lower band is
asked what rate the cases it measured achieved; a release blocking band is asked
whether it measured what it selected at all.

**The sentence this replaces was the defect.** It read that P0 and P1 need
nothing like this, because "any P0 or P1 observation not passing fails the run"
and "this band had a failure" are the same statement. They are not: a skipped
case is an observation not passing, and an exit status cannot see one. claude
band P1 reported success at seven of eleven, four blocking cases having skipped
behind failed foundations.

**A harness error is still fatal.** An ``error`` in the report is an
instrument defect and
the floor is a statement about the model, so a band carrying one refuses rather
than being averaged. That distinction is the reason the band has a floor at all.

**The floor is imported, never restated.** ``Thresholds.pass_floor`` is the
project's standard and a second copy would eventually disagree with the first.
"""

import argparse
import logging
from pathlib import Path
from typing import Final, Optional
from xml.etree import ElementTree

from cmn.band_summary import (
    _DEPENDENCY_SKIP, _QUARANTINE_SKIP, _code_in, skip_detail_lines,
)
from cmn.quarantine_file import load_quarantine_for
from cmn.verdict import Thresholds
from cmn.threshold_domain import check_rate

logger = logging.getLogger(__name__)

_ENCODING: Final[str] = "utf-8"

# `cmn_verdict_and_cli.md` section 7.3 chose the verdict tool's codes to stay
# clear of argparse, which exits 2. These mirror them: a band below the floor is
# a finding about the model, and an unreadable report is a refusal.
_EXIT_GREEN: Final[int] = 0
_EXIT_BELOW_FLOOR: Final[int] = 1
_EXIT_REFUSED: Final[int] = 4

# THE STATUS A BAND'S RUN REPORTED, handed here rather than left to fail the
# job. A composite action step cannot carry `continue-on-error`, so the step
# running the band would otherwise decide it (section 3.12.2).
_UNREPORTED: Final[int] = -1

# WHERE THE HARNESS PUTS A MISSING ARTIFACT on each case it skipped for one
# (harness `cmn/missing_artifact.py`).
_KIND_PROPERTY: Final[str] = "mqc_artifact_kind"
_PATH_PROPERTY: Final[str] = "mqc_artifact_path"


def run_status_problem(status: int) -> Optional[str]:
    """Return why a band's run status leaves nothing to weigh, or ``None``.

    **Only the graded-failure code is the floor's business.** It says cases
    failed, which is what a rate exists to measure. Every other nonzero status
    is an instrument defect: a collection error, a usage error, a precondition
    that did not hold, and none of those measured a model.

    Args:
        status (int): The exit status the band's run reported, or ``-1`` where
            it reported none.

    Returns:
        Optional[str]: The refusal to report, or ``None`` where the floor
        decides.
    """
    if status == _UNREPORTED:
        return (
            "the band's run reported no exit status, so whether it ran at all "
            "is unknown and no rate from its report is a statement about the model"
        )
    if status in (_EXIT_GREEN, _EXIT_BELOW_FLOOR):
        return None
    return (
        f"the band's run exited {status}, which is neither a clean run nor the "
        f"graded-failure code, so it is an instrument defect rather than a "
        f"model that underperformed"
    )


def _counts(report: Path) -> tuple[int, int, int, int]:
    """Return the cases, failures, errors and skips a report carries.

    Args:
        report (Path): The JUnit XML a band produced.

    Returns:
        tuple: Total cases, failures, errors and skips.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when the report is absent
            or will not parse. **Refused rather than treated as zero cases**: a
            band that produced no report measured nothing, and a rate over an
            empty denominator would read as a pass.
    """
    if not report.is_file():
        raise ValueError(f"QC_HARNESS_PARSER_ERROR: no band report at {report}")
    try:
        tree = ElementTree.parse(report)
    except ElementTree.ParseError as error:
        raise ValueError(
            f"QC_HARNESS_PARSER_ERROR: band report at {report} will not parse"
        ) from error

    cases = list(tree.iter("testcase"))
    failures = sum(1 for case in cases if case.find("failure") is not None)
    errors = sum(1 for case in cases if case.find("error") is not None)
    skips = sum(1 for case in cases if case.find("skipped") is not None)
    return len(cases), failures, errors, skips


def assess_blocking(
    report: Path,
    quarantined: frozenset[str] = frozenset(),
) -> tuple[int, str]:
    """Return the exit code for a release blocking band and why.

    **Every case the band selected was measured and passed, or the band fails.**
    A skip is not a pass and not a failure; it is an absence, and a band that
    exists to block a release cannot report green on an absence.

    **Whatever caused the skip, and nothing releases one.** A foundation that
    did not hold, a fixture gone stale, a budget exhausted: each means the case
    was not measured. Design: ``consumer_ci.md`` sections 3.12.2 and 3.12.5.

    Args:
        report (Path): The band's JUnit XML.
        quarantined (frozenset[str]): Case identifiers declared quarantined,
            which only name a skip's cause: a quarantined case is deselected
            and never reaches a band.

    Returns:
        tuple: The exit code and a message naming the figures behind it.
    """
    try:
        selected, failures, errors, skipped = _counts(report)
    except ValueError as error:
        return _EXIT_REFUSED, str(error)

    if errors:
        return (
            _EXIT_REFUSED,
            f"{errors} case(s) reported an error rather than a failure, which "
            f"is an instrument defect and not a measurement of a model",
        )
    if not selected:
        return (
            _EXIT_REFUSED,
            "the band collected no case, so it established nothing about a "
            "band that blocks a release",
        )

    # NO SKIP IS RELEASED. A quarantined case is deselected and never reaches
    # here, so every skip is a case this band selected and did not measure
    # (`consumer_ci.md` section 3.12.5).
    passed = selected - failures - skipped
    executed = selected - skipped

    # SKIPPED IS A STATE AND IT HAS A CAUSE. "Not measured" names no outcome a
    # reader can act on, and the remedy differs: a dependency skip clears when
    # the band above it is fixed, and one of ours is ours. The project owner's
    # correction, 2026-10-07.
    # ALL FIVE, ALWAYS, INCLUDING A ZERO, which is the shape the harness band
    # line states for the same reason: a reader comparing two engines must not
    # be comparing two formats (harness `code-style.md` section 7.1).
    counted = [
        f"{selected} total", f"{executed} executed",
        f"{passed} passed", f"{failures} failed", f"{skipped} skipped",
    ]
    causes = _skip_causes(report, quarantined)
    # THE COUNTS FIRST, THEN ONE LINE PER CAUSE. A reader needs the shape of
    # the band before its reasons (harness design section 7.11.3).
    # ONE FACT PER LINE. The verdict after a cause carrying its own colon
    # put two in one sentence, which `code-style.md` section 7 refuses,
    # and a reader scanning for the counts had to parse past the reasons.
    detail = "\n".join([", ".join(counted), *causes])

    # THE LINE STATES THE RESULT, not the rule behind it (`code-style.md`
    # section 7.1). What a blocking band answers for is in `consumer_ci.md`
    # section 3.12.2, and a failing line names its cause because the cause is
    # what a reader acts on.
    # SKIPS THE ENVIRONMENT CAUSED, AND NOTHING ELSE, ARE NOT MEASURED. A
    # failure or a skip behind a failed foundation is below the blocking floor
    # (design section 3.12.2).
    environmental = _environmental_skips(report) if skipped and not failures else []
    if environmental and len(environmental) == skipped:
        return _EXIT_REFUSED, _not_measured(environmental, selected, detail)
    if failures or skipped:
        return _EXIT_BELOW_FLOOR, f"{detail}\nbelow the blocking floor"
    return _EXIT_GREEN, detail


def _skip_causes(report: Path, quarantined: frozenset[str]) -> list[str]:
    """Return one line per distinct skip cause, from the shared enumeration.

    **One implementation, two callers.** The harness band line and this gate
    described the same skips in their own words until 2026-10-09, and the gate's
    words were the vaguer: "for a reason of ours" covered nineteen codes taking
    five different remedies (harness design section 7.11.3).

    Args:
        report (Path): The band's JUnit XML.
        quarantined (frozenset[str]): The declared identifiers, which supply a
            code for a case skipped before its message could carry one.

    Returns:
        list[str]: One line per cause, empty where nothing was skipped.
    """
    skips: list[tuple[str, str]] = []
    for case in ElementTree.parse(report).iter("testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        reason = str(skipped.get("message", ""))
        name = str(case.get("name", ""))
        if not reason.strip().startswith("QC_") and quarantined and any(
            entry and entry in name for entry in quarantined
        ):
            reason = f"{_QUARANTINE_SKIP}: declared for this engine"
        skips.append((name, reason))
    return skip_detail_lines(skips)


def assess(report: Path, floor: Optional[float] = None) -> tuple[int, str]:
    """Return the exit code for a band and the sentence explaining it.

    **A skip is not passed, and the denominator is every case the band
    selected.** A quarantined case is never selected, so nothing here excuses
    one. A band that measured none refuses rather than scoring zero. Design:
    ``consumer_ci.md`` section 3.12.2.

    Args:
        report (Path): The band's JUnit XML.
        floor (Optional[float]): The minimum pass rate, defaulting to the
            project's own ``Thresholds``.

    Returns:
        tuple: The exit code and a message naming the figures behind it.
    """
    if floor is None:
        required = Thresholds().pass_floor
    else:
        # THE OVERRIDE IS CHECKED AGAINST THE SAME DOMAIN AS THE DEFAULT, and
        # by the harness's own predicate rather than a restatement of it. A
        # floor of 0 passed every band and 100 failed every band, silently and
        # with the tool's ordinary green or red. Design section 3.12.2.
        try:
            check_rate("floor", floor)
        except ValueError as error:
            return _EXIT_REFUSED, str(error)
        required = floor
    try:
        total, failures, errors, skips = _counts(report)
    except ValueError as error:
        return _EXIT_REFUSED, str(error)

    if errors:
        return (
            _EXIT_REFUSED,
            f"{errors} case(s) reported an error rather than a failure, which is "
            f"an instrument defect: a floor is a statement about the model and "
            f"this band "
            f"did not measure one",
        )

    measured = total - skips
    if measured <= 0:
        return (
            _EXIT_REFUSED,
            f"the band collected {total} case(s) and measured none, so there is "
            f"no rate to compare against the floor",
        )

    passed = measured - failures
    rate = passed / total
    detail = (
        f"{passed} of {total} selected passed ({rate:.1%}), {failures} failed, "
        f"{skips} skipped, floor {required:.0%}"
    )
    if rate < required:
        return _below_floor(report, passed, total, required, detail)
    return _EXIT_GREEN, f"the band cleared its floor: {detail}"


def _below_floor(
    report: Path, passed: int, total: int, required: float, detail: str
) -> tuple[int, str]:
    """Return the outcome of a band whose rate is below its floor.

    **Below the floor only where the measured cases put it there.** Counting
    the environment's skips as passes, a band that clears was not measured,
    and saying so is not a statement about the model (design section 3.12.2).

    Args:
        report (Path): The band's JUnit XML.
        passed (int): The cases that passed.
        total (int): The cases the band selected.
        required (float): The floor.
        detail (str): The band's counts.

    Returns:
        tuple: ``4`` and the not-measured line, or ``1`` and the below-floor line.
    """
    environmental = _environmental_skips(report)
    if environmental and (passed + len(environmental)) / total >= required:
        return _EXIT_REFUSED, _not_measured(environmental, total, detail)
    return _EXIT_BELOW_FLOOR, f"the band is below its floor: {detail}"


def _environmental_skips(report: Path) -> list[str]:
    """Return the code of each skip the environment caused, one per skipped case.

    **Environmental is every harness skip but two**: an unmet foundation, which
    is a result one layer up, and a quarantine, which is a known finding.
    Design: ``consumer_ci.md`` section 3.12.2.

    Args:
        report (Path): The band's JUnit XML, already read once.

    Returns:
        list[str]: The codes, in report order.
    """
    codes: list[str] = []
    for case in ElementTree.parse(report).iter("testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        code = _code_in(str(skipped.get("message", "")))
        if code.startswith("QC_HARNESS_") and code not in (_DEPENDENCY_SKIP, _QUARANTINE_SKIP):
            codes.append(code)
    return codes


def _not_measured(environmental: list[str], total: int, detail: str) -> str:
    """State a band the environment's skips took below its floor.

    Args:
        environmental (list[str]): The environmental skips' codes.
        total (int): The cases the band selected.
        detail (str): The band's counts.

    Returns:
        str: The line naming how many cases the environment skipped and on
        which codes, then the counts.
    """
    named = ", ".join(sorted(set(environmental)))
    return (
        f"the band was not measured: the environment skipped {len(environmental)} "
        f"of {total} selected cases on {named}\n{detail}"
    )


def _missing_artifacts(report: Path) -> list[str]:
    """Return one line per artifact the band's cases skipped for, naming its kind and path.

    The harness's skip line names the code and what it means, not which file,
    so the floor reads the ``mqc_artifact_kind`` and ``mqc_artifact_path``
    properties each such case carries. Design: ``consumer_ci.md`` section 3.12.2.

    Args:
        report (Path): The band's JUnit XML.

    Returns:
        list[str]: ``missing artifact <kind> <path>, <n> case(s) skipped for
        it``, in order of first appearance; empty where none was missing or the
        report cannot be read, which the assessment already reports.
    """
    try:
        tree = ElementTree.parse(report)
    except (OSError, ElementTree.ParseError):
        return []
    counted: dict[tuple[str, str], int] = {}
    for case in tree.iter("testcase"):
        if case.find("skipped") is None:
            continue
        properties = {
            str(found.get("name")): str(found.get("value", ""))
            for found in case.iter("property")
        }
        kind = properties.get(_KIND_PROPERTY)
        if kind:
            artifact = (kind, properties.get(_PATH_PROPERTY, ""))
            counted[artifact] = counted.get(artifact, 0) + 1
    return [
        f"missing artifact {kind} {path}, {count} case(s) skipped for it"
        for (kind, path), count in counted.items()
    ]


def _declared_quarantine(engine: str) -> frozenset[str]:
    """Return the case identifiers quarantined for one engine.

    **An absent file is a starting condition, not an error**, which is what the
    harness loader already answers: a repository with nothing quarantined has
    no quarantine file.

    Args:
        engine (str): Which engine ran, naming the file.

    Returns:
        frozenset[str]: The declared identifiers, empty where none are.
    """
    if not engine:
        return frozenset()
    entries = load_quarantine_for(Path("config"), engine)
    return frozenset(str(entry.case_id) for entry in entries)


def main(argv: Optional[list[str]] = None) -> int:
    """Assess one band report and return its exit code.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.

    Returns:
        int: ``0`` cleared, ``1`` below the floor, ``4`` refused.
    """
    parser = argparse.ArgumentParser(
        prog="band-floor",
        description="Compare a lower-priority band's pass rate against the floor",
    )
    parser.add_argument("report", type=Path, help="The band's JUnit XML")
    parser.add_argument(
        "--floor",
        type=float,
        default=None,
        help="Override the floor, for testing the boundary rather than the policy",
    )
    parser.add_argument(
        "--blocking",
        action="store_true",
        help=(
            "Assess a release blocking band: every case selected was measured "
            "and passed"
        ),
    )
    parser.add_argument(
        "--engine",
        default="",
        help="Which engine ran, naming the quarantine file a skip's cause is read from",
    )
    parser.add_argument(
        "--run-status",
        type=int,
        default=_EXIT_GREEN,
        help=(
            "The exit status the band's run reported, which the floor weighs "
            "rather than the job taking it; -1 where none was reported"
        ),
    )
    parsed = parser.parse_args(argv)

    if parsed.blocking:
        code, message = assess_blocking(
            parsed.report, _declared_quarantine(parsed.engine)
        )
    else:
        code, message = assess(parsed.report, parsed.floor)
    lines = [message, *_missing_artifacts(parsed.report)]

    # ASSESSED AND REPORTED EVEN WHERE THE STATUS REFUSES, so a band whose run
    # exited 3 still names what it held and the artifact it was missing; the
    # status, not the rate, then decides it. Design section 3.12.2.
    problem = run_status_problem(parsed.run_status)
    if problem is not None:
        for line in lines:
            logger.error("%s", line)
        logger.error("%s", problem)
        return _EXIT_REFUSED

    # LOGGED, NOT ALSO PRINTED. `basicConfig` below sends this to stderr, and
    # doing both put every verdict on the console twice.
    for line in lines:
        if code == _EXIT_GREEN:
            logger.info("%s", line)
        else:
            logger.error("%s", line)
    return code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
