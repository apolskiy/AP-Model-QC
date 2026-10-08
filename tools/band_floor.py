# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Decide whether a lower-priority band cleared its pass floor.

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

**A harness error is still fatal.** An ``error`` in the report is our defect and
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

from cmn.band_summary import _DEPENDENCY_SKIP, _QUARANTINE_SKIP
from cmn.config import load_quarantine_for
from cmn.quarantine import released_by_dispensation
from cmn.verdict import Thresholds

logger = logging.getLogger(__name__)

_ENCODING: Final[str] = "utf-8"

# `cmn_verdict_and_cli.md` section 7.3 chose the verdict tool's codes to stay
# clear of argparse, which exits 2. These mirror them: a band below the floor is
# a finding about the model, and an unreadable report is a refusal.
_EXIT_GREEN: Final[int] = 0
_EXIT_BELOW_FLOOR: Final[int] = 1
_EXIT_REFUSED: Final[int] = 4


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
    dispensed: Optional[dict[str, str]] = None,
) -> tuple[int, str]:
    """Return the exit code for a release blocking band and why.

    **Every case the band selected was measured and passed, or the band fails.**
    A skip is not a pass and not a failure; it is an absence, and a band that
    exists to block a release cannot report green on an absence.

    **Whatever caused the skip.** A foundation that did not hold, a fixture gone
    stale, a budget exhausted, a quarantine entry: each means the case was not
    measured, which is the one answer a blocking band may not round up.

    **A recorded dispensation is the one release**, and the message names the
    case and the reference so a reader can go and read what was agreed. Harness
    design section 4.6.13.

    Args:
        report (Path): The band's JUnit XML.
        quarantined (frozenset[str]): Case identifiers declared quarantined.
            They do not leave the denominator: quarantine saves the run's cost
            and buys nothing else.
        dispensed (Optional[dict]): Each case product management has accepted a
            release with, mapped to the tracker reference announcing it.

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
            f"is our defect and not a measurement of a model",
        )
    if not selected:
        return (
            _EXIT_REFUSED,
            "the band collected no case, so it established nothing about a "
            "band that blocks a release",
        )

    # QUARANTINE DOES NOT EXCUSE A BLOCKING BAND. It exists to stop spending
    # on a case already known to fail, not to let one release: a quarantined
    # P0 or P1 still blocks. The project owner's correction, 2026-10-07;
    # `consumer_ci.md` section 3.12.2.
    #
    # A RECORDED DISPENSATION IS THE ONE EXCEPTION, and it is an exception
    # rather than a mechanism: it is written only once product management has
    # announced the decision in the tracker (harness section 4.6.13).
    released = _released_skips(report, dispensed or {})
    unmeasured = skipped - len(released)
    passed = selected - failures - skipped
    executed = selected - skipped

    # SKIPPED IS A STATE AND IT HAS A CAUSE. "Not measured" names no outcome a
    # reader can act on, and the remedy differs: a dependency skip clears when
    # the band above it is fixed, and one of ours is ours. The project owner's
    # correction, 2026-10-07.
    counted = [
        f"{selected} total", f"{executed} executed",
        f"{passed} passed", f"{failures} failed",
    ]
    counted.extend(_skip_phrases(report, quarantined))
    if released:
        counted.append(
            f"{len(released)} released on a recorded dispensation "
            f"({'; '.join(released)})"
        )
    detail = ", ".join(counted)

    # THE LINE STATES THE RESULT, not the rule behind it (`code-style.md`
    # section 7.1). What a blocking band answers for is in `consumer_ci.md`
    # section 3.12.2, and a failing line names its cause because the cause is
    # what a reader acts on.
    if failures or unmeasured:
        return _EXIT_BELOW_FLOOR, f"{detail}: below the blocking floor"
    return _EXIT_GREEN, detail


def _skip_phrases(report: Path, quarantined: frozenset[str]) -> list[str]:
    """Return one phrase per kind of skip, naming its cause.

    **A skip is a state and its cause decides the remedy.** A case skipped
    behind a higher band clears when that band is fixed; one skipped on a
    fixture or a budget is ours; one quarantined was a decision.

    Args:
        report (Path): The band's JUnit XML.
        quarantined (frozenset[str]): The declared identifiers.

    Returns:
        list[str]: Phrases for the kinds present, in a stable order, and empty
        where nothing was skipped.
    """
    kinds: dict[str, int] = {}
    for case in ElementTree.parse(report).iter("testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        name = str(case.get("name", ""))
        reason = str(skipped.get("message", ""))
        if _QUARANTINE_SKIP in reason or (
            quarantined and any(entry and entry in name for entry in quarantined)
        ):
            key = "skipped as a known failure in quarantine"
        elif _DEPENDENCY_SKIP in reason:
            key = "skipped behind a higher band failure"
        else:
            key = "skipped for a reason of ours"
        kinds[key] = kinds.get(key, 0) + 1
    # THE SAME THREE PHRASES THE HARNESS BAND LINE USES, so a band's own line
    # and this gate cannot name one skip two ways (`code-style.md` section 7.1).
    order = (
        "skipped behind a higher band failure",
        "skipped as a known failure in quarantine",
        "skipped for a reason of ours",
    )
    return [f"{kinds[key]} {key}" for key in order if key in kinds]


def _released_skips(report: Path, dispensed: dict[str, str]) -> list[str]:
    """Return one phrase per skipped case a recorded dispensation releases.

    **Matched on the identifier inside the test name**, because a JUnit name
    carries the whole callable and a dispensation names the case.

    Args:
        report (Path): The band's JUnit XML.
        dispensed (dict): Case identifier to the tracker reference.

    Returns:
        list[str]: ``"<case> per <reference>"`` for each, sorted so a message
        does not depend on report order.
    """
    if not dispensed:
        return []
    released: list[str] = []
    for case in ElementTree.parse(report).iter("testcase"):
        if case.find("skipped") is None:
            continue
        name = str(case.get("name", ""))
        for case_id, reference in dispensed.items():
            if case_id and case_id in name:
                released.append(f"{case_id} per {reference}")
    return sorted(released)


def _quarantined_skips(report: Path, quarantined: frozenset[str]) -> int:
    """Return how many skipped cases were declared quarantined.

    **Matched on the identifier inside the test name**, because a JUnit name
    carries the whole callable and a quarantine entry names the case.

    Args:
        report (Path): The band's JUnit XML.
        quarantined (frozenset[str]): The declared identifiers.

    Returns:
        int: How many skips a declaration excuses.
    """
    if not quarantined:
        return 0
    excused = 0
    for case in ElementTree.parse(report).iter("testcase"):
        if case.find("skipped") is None:
            continue
        name = str(case.get("name", ""))
        if any(entry and entry in name for entry in quarantined):
            excused += 1
    return excused


def assess(report: Path, floor: Optional[float] = None) -> tuple[int, str]:
    """Return the exit code for a band and the sentence explaining it.

    **Skips leave the denominator.** A case whose foundation did not hold
    produced no measurement, so counting it as a failure would charge the band
    for a defect belonging to an earlier one, and counting it as a pass would
    invent a result.

    Args:
        report (Path): The band's JUnit XML.
        floor (Optional[float]): The minimum pass rate, defaulting to the
            project's own ``Thresholds``.

    Returns:
        tuple: The exit code and a message naming the figures behind it.
    """
    required = Thresholds().pass_floor if floor is None else floor
    try:
        total, failures, errors, skips = _counts(report)
    except ValueError as error:
        return _EXIT_REFUSED, str(error)

    if errors:
        return (
            _EXIT_REFUSED,
            f"{errors} case(s) reported an error rather than a failure, which is "
            f"our defect: a floor is a statement about the model and this band "
            f"did not measure one",
        )

    measured = total - skips
    if measured <= 0:
        return (
            _EXIT_REFUSED,
            f"the band collected {total} case(s) and measured none, so there is "
            f"no rate to compare against the floor",
        )

    rate = (measured - failures) / measured
    detail = (
        f"{measured - failures} of {measured} measured passed "
        f"({rate:.1%}), {skips} skipped, floor {required:.0%}"
    )
    if rate < required:
        return _EXIT_BELOW_FLOOR, f"the band is below its floor: {detail}"
    return _EXIT_GREEN, f"the band cleared its floor: {detail}"


def _declared_dispensations(engine: str) -> dict[str, str]:
    """Return each case a recorded release decision excuses, and the reference.

    **An unconfirmed entry carries none**, which the harness decides: an entry
    without an observed date or model is our bookkeeping failing, and a
    dispensation on top of that accepts a release against a finding whose
    expiry cannot be evaluated.

    Args:
        engine (str): Which engine ran, naming the file.

    Returns:
        dict[str, str]: Case identifier to tracker reference, empty where none
        is recorded.
    """
    if not engine:
        return {}
    return {
        str(entry.case_id): released_by_dispensation(entry)
        for entry in load_quarantine_for(Path("config"), engine)
        if released_by_dispensation(entry)
    }


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
            "and passed, quarantined cases excepted"
        ),
    )
    parser.add_argument(
        "--engine",
        default="",
        help="Which engine ran, naming the quarantine file to honour",
    )
    parsed = parser.parse_args(argv)

    if parsed.blocking:
        code, message = assess_blocking(
            parsed.report,
            _declared_quarantine(parsed.engine),
            _declared_dispensations(parsed.engine),
        )
    else:
        code, message = assess(parsed.report, parsed.floor)
    # LOGGED, NOT ALSO PRINTED. `basicConfig` below sends this to stderr, and
    # doing both put every verdict on the console twice.
    if code == _EXIT_GREEN:
        logger.info("%s", message)
    else:
        logger.error("%s", message)
    return code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
