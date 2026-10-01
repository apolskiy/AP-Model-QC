# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Decide whether a lower-priority band cleared its pass floor.

Specified by ``docs/design/consumer_ci.md`` section 3.12.2.

**P0 and P1 need nothing like this.** "Any P0 or P1 observation not passing
fails the run" and "this band had a failure" are the same statement, so pytest's
exit status enforces V1 by itself. P2-P4 is the only band where a failure is not
automatically fatal, so it is the only one that needs a rate.

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
    parsed = parser.parse_args(argv)

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
