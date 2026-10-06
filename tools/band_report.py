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

Usage::

    python -m tools.band_report reports/junit_mqc_p0.xml --priority 0
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from cmn.band_summary import band_lines


def counts_from(report: Path) -> tuple[int, int, list[str]]:
    """Return passed, failed and each skip's reason from a JUnit report.

    **A case carrying neither failure, error nor skip passed.** JUnit records
    the exceptions rather than the successes, so a pass is an absence.

    Args:
        report (Path): The JUnit XML a run wrote.

    Returns:
        tuple: Passed count, failed count, and one reason per skipped case.
    """
    passed = failed = 0
    reasons: list[str] = []
    for case in ElementTree.parse(report).getroot().iter("testcase"):
        skipped = case.find("skipped")
        if skipped is not None:
            reasons.append(str(skipped.get("message", "")))
            continue
        if case.find("failure") is not None or case.find("error") is not None:
            failed += 1
            continue
        passed += 1
    return passed, failed, reasons


def main(argv: Optional[list[str]] = None) -> int:
    """Print the band line for one report.

    Args:
        argv (Optional[list]): Arguments, or None to read the command line.

    Returns:
        int: Zero, including where the report is absent: a summary step must
        not fail the job it is describing.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--priority", default="")
    parsed = parser.parse_args(argv)

    if not parsed.report.is_file():
        print(f"No report at {parsed.report}, so this band ran nothing.")
        return 0

    passed, failed, reasons = counts_from(parsed.report)
    lines = band_lines(
        passed=passed, failed=failed, skip_reasons=reasons,
        priority=parsed.priority,
    )
    for line in lines or ["This band selected nothing."]:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
