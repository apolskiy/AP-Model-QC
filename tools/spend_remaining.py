# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The remainder a live band may spend, read from what the earlier live bands published.

Created: 2026-11-12
Last updated: 2026-11-17

This file contains ``MissingSpendReport``, an earlier band's report that is
missing or cannot be read; ``remaining``, which subtracts every earlier live
band's published ``mqc.total_spend_usd`` from the dispatch's ceiling; and
``main``, the command line a live band job runs before its band to write the
remainder its band step passes as ``--max-spend``.

The remainder is rounded down to the cent. A remainder of zero or less refuses
with ``QC_HARNESS_BUDGET_EXHAUSTED`` and exit ``4``. Fewer or more reports than
live bands ran before, or a report that is empty, will not parse or lacks one
priced total, is declared missing: ``main`` writes ``missing=spend_report=<path>``
and a remainder of ``0.01`` and exits ``0``, so the band runs with
``--missing-artifact`` and every case skips.

Specified by ``docs/design/consumer_ci.md`` section 7.8.4.
"""

import argparse
import logging
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Final, Optional
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

_EXIT_WRITTEN: Final[int] = 0
_EXIT_REFUSED: Final[int] = 4

_EXHAUSTED: Final[str] = "QC_HARNESS_BUDGET_EXHAUSTED"
_MISSING: Final[str] = "QC_HARNESS_ARTIFACT_MISSING"

# WHAT A BAND MISSING A SPEND REPORT RUNS WITH: above zero, so its own total
# stays priced, and a cent, so nothing it dispatched could spend more.
_DECLARED_REMAINDER: Final[str] = "0.01"

# THE PROPERTY A RUN'S JUNIT REPORT CARRIES ITS SPEND UNDER (harness
# `cmn_verdict_and_cli.md` section 5.6.4).
_TOTAL: Final[str] = "mqc.total_spend_usd"
_CENT: Final[Decimal] = Decimal("0.01")


class MissingSpendReport(ValueError):
    """An earlier band's spend report that is missing or cannot be read.

    Attributes:
        path (Path): The report, or the reports directory where the count is wrong.
        detail (str): What was wrong.
    """

    def __init__(self, path: Path, detail: str) -> None:
        """Build the record, its message the missing-artifact skip's.

        Args:
            path (Path): The report, or the reports directory.
            detail (str): What was wrong.

        Returns:
            None
        """
        super().__init__(f"{_MISSING}: spend_report {path}, {detail}")
        self.path = path
        self.detail = detail


def _published_total(report: Path) -> Decimal:
    """Return the total one band's report published.

    Args:
        report (Path): A band's JUnit XML.

    Returns:
        Decimal: The priced total in USD.

    Raises:
        MissingSpendReport: Naming the report, when it is empty or will not
            parse, or publishes no total, several, or an unpriced one.
    """
    try:
        tree = ElementTree.parse(report)
    except ElementTree.ParseError as error:
        raise MissingSpendReport(report, "will not parse, so its spend is unknown") from error
    values = [str(found.get("value", "")) for found in tree.iter("property")
              if found.get("name") == _TOTAL]
    if len(values) != 1:
        raise MissingSpendReport(report, f"publishes {len(values)} {_TOTAL} value(s)")
    try:
        return Decimal(values[0])
    except InvalidOperation as error:
        raise MissingSpendReport(
            report, f"publishes {_TOTAL}={values[0]!r}, which is not a priced total"
        ) from error


def remaining(ceiling: Decimal, reports: Path, earlier: int) -> Decimal:
    """Return what the ceiling leaves after every earlier live band, rounded down to the cent.

    Args:
        ceiling (Decimal): The dispatch's ``max_spend``.
        reports (Path): The directory holding the earlier live bands' reports.
        earlier (int): How many live bands ran before this one.

    Returns:
        Decimal: The remainder, above zero.

    Raises:
        MissingSpendReport: Naming the directory when fewer or more reports
            arrived than live bands ran before, or the report that cannot be
            read.
        ValueError: With ``QC_HARNESS_BUDGET_EXHAUSTED`` when the remainder is
            zero or less.
    """
    found = sorted(reports.glob("*.xml")) if earlier and reports.is_dir() else []
    if len(found) != earlier:
        raise MissingSpendReport(
            reports,
            f"{earlier} live band(s) ran before this one and {len(found)} report(s) "
            f"arrived, so what they spent is unknown",
        )
    spent = sum((_published_total(report) for report in found), Decimal("0"))
    left = (ceiling - spent).quantize(_CENT, rounding=ROUND_FLOOR)
    if left <= 0:
        raise ValueError(
            f"{_EXHAUSTED}: the earlier live bands spent ${spent} of the ${ceiling} ceiling"
        )
    return left


def main(argv: Optional[list[str]] = None) -> int:
    """Write the remainder a live band may spend, or refuse.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.

    Returns:
        int: ``0`` wrote the remainder, or declared a report missing with the
        one-cent remainder; ``4`` refused an exhausted ceiling.
    """
    parser = argparse.ArgumentParser(
        prog="spend-remaining",
        description="Write what the dispatch's ceiling leaves for the next live band",
    )
    parser.add_argument("--ceiling", type=Decimal, required=True,
                        help="The dispatch's max_spend in USD")
    parser.add_argument("--reports", type=Path, required=True,
                        help="The directory the earlier live bands' reports were taken into")
    parser.add_argument("--earlier", type=int, required=True,
                        help="How many live bands ran before this one")
    parser.add_argument("--output", type=Path, required=True,
                        help="Where to append remaining=<USD>, the step output file")
    parsed = parser.parse_args(argv)
    try:
        left = remaining(parsed.ceiling, parsed.reports, parsed.earlier)
    except MissingSpendReport as missing:
        # THE BAND RUNS AND EVERY CASE SKIPS, naming the report (design section
        # 7.8.4).
        logger.error("%s", missing)
        with parsed.output.open("a", encoding="utf-8") as output:
            output.write(f"remaining={_DECLARED_REMAINDER}\n"
                         f"missing=spend_report={missing.path}\n")
        return _EXIT_WRITTEN
    except ValueError as error:
        logger.error("%s", error)
        return _EXIT_REFUSED
    with parsed.output.open("a", encoding="utf-8") as output:
        output.write(f"remaining={left}\n")
    logger.info("Remainder for this band: $%s of $%s", left, parsed.ceiling)
    return _EXIT_WRITTEN


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
