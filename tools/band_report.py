# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The band line, from a run's JUnit XML, for a job summary.

Specified by the harness ``cmn_verdict_and_cli.md`` section 7.11.

**Read from the report rather than the console.** The band line is printed by
`pytest_terminal_summary` and a workflow step that piped the run to capture it
would change the exit status of the thing being measured, which is the trap
this project walked into once already: a pipeline returns its last command's
status unless `pipefail` is set, so a failing band would have reported success.

**The arithmetic is the harness's**, imported rather than repeated, so the job
summary and the console cannot disagree.

**The overall report is a per-band table, not a single figure.** A release
question is answered by the blocking bands: a run at 95% overall with one P0
failure does not ship, so a total on its own tells a reader nothing they can
act on.

Usage::

    python -m tools.band_report reports/junit_mqc_p0.xml --priority 0

    python -m tools.band_report --overall \
        reports/junit_mqc_p0.xml reports/junit_mqc_p1.xml \
        reports/junit_mqc_p2p4.xml \
        --priority 0 --priority 1 --priority 2,3,4
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from cmn.band_summary import band_table, result_lines


def counts_from(report: Path) -> tuple[int, int, list[tuple[str, str]]]:
    """Return passed, failed and each skip's reason from a JUnit report.

    **A case carrying neither failure, error nor skip passed.** JUnit records
    the exceptions rather than the successes, so a pass is an absence.

    Args:
        report (Path): The JUnit XML a run wrote.

    Returns:
        tuple: Passed count, failed count, and one ``(case, reason)`` pair per
        skipped case. **The pair rather than the reason alone**, because a skip
        is reported on its own line against the case it belongs to (harness
        design section 7.11.3).
    """
    passed = failed = 0
    skips: list[tuple[str, str]] = []
    for case in ElementTree.parse(report).getroot().iter("testcase"):
        skipped = case.find("skipped")
        if skipped is not None:
            skips.append(
                (str(case.get("name", "")), str(skipped.get("message", "")))
            )
            continue
        if case.find("failure") is not None or case.find("error") is not None:
            failed += 1
            continue
        passed += 1
    return passed, failed, skips


def main(argv: Optional[list[str]] = None) -> int:
    """Print the band line for one report.

    Args:
        argv (Optional[list]): Arguments, or None to read the command line.

    Returns:
        int: Zero, including where the report is absent: a summary step must
        not fail the job it is describing.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, nargs="+")
    parser.add_argument(
        "--priority", action="append", default=None,
        help="The band each report covers, repeated once per report",
    )
    parser.add_argument(
        "--overall", action="store_true",
        help="Render a per-band table with totals rather than one band's lines",
    )
    parsed = parser.parse_args(argv)

    bands = parsed.priority or [""]
    if len(bands) != len(parsed.report):
        print(
            f"{len(parsed.report)} report(s) and {len(bands)} band label(s), "
            f"so a row could not be attributed. Pass one --priority per report."
        )
        return 0

    measured: list[tuple[str, int, int, list[str]]] = []
    for report, band in zip(parsed.report, bands):
        if not report.is_file():
            print(f"No report at {report}, so that band ran nothing.")
            continue
        passed, failed, reasons = counts_from(report)
        measured.append((band, passed, failed, reasons))

    if not measured:
        return 0

    if parsed.overall:
        for line in band_table(measured) or ["Nothing was measured."]:
            print(line)
        return 0

    for band, passed, failed, skips in measured:
        lines = result_lines(
            passed=passed, failed=failed, skips=skips, priority=band,
        )
        for line in lines or ["This band selected nothing."]:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
