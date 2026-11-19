# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""State what a debug run's pytest step did, and fail when pytest stopped.

Created: 2026-11-19
Last updated: 2026-11-19

This file contains ``stopped_causes``, which reads a JUnit report and returns
why pytest ran no case, empty when it ran; ``outcome_lines``, which returns a
ran report's counts one per line, total, executed, passed, passw, failed and
skipped, with broken added when a case crashed; ``summary_lines``, which
renders either as the run summary's first section; and ``main``, the command
line that appends that section to ``--summary`` and exits 0 when pytest ran,
1 when it stopped.

``debug-cases-on-demand.yml`` runs it straight after the pytest step of each
debug job, whatever that step did. The pytest step continues on error, because
a failed case is what a debug run looks at, so this is what tells a run that
measured something from one that measured nothing.

**The section opens with a headline**: ``Outcome: FAILED``, ``PASSED`` or
``NOTHING EXECUTED``, then the counts. A ran report lists every case that did
not pass with its outcome and message. A stopped one gives each cause and the
error it ended on.

A failed, skipped or broken case exits 0: the counts state it, and a debug run
carries no verdict. **Pytest stopping exits 1**: the report missing,
unreadable or holding no case, or holding a ``collection failure`` or
``internal error`` testcase, the two pytest writes for a session that stopped
before running a case.

Specified by ``docs/design/consumer_ci.md`` section 6.5.3.
"""

import argparse
import sys
from pathlib import Path
from typing import Final, Optional
from xml.etree import ElementTree

_SESSION_ERRORS: Final[tuple[str, ...]] = ("collection failure", "internal error")
_ENCODING: Final[str] = "utf-8"
_COUNTED: Final[tuple[str, ...]] = ("passed", "passw", "failed", "skipped")
_PROBLEMS: Final[tuple[tuple[str, str], ...]] = (
    ("error", "broken"), ("failure", "failed"), ("skipped", "skipped"))
_MESSAGE_LIMIT: Final[int] = 300


def _testcases(report: Path) -> list[ElementTree.Element]:
    """Return every testcase in a JUnit report.

    Args:
        report (Path): The report.

    Returns:
        list: The ``testcase`` elements, in report order.

    Raises:
        ValueError: When the report is missing or will not parse.
    """
    if not report.is_file():
        raise ValueError(f"no JUnit report at {report}")
    try:
        return list(ElementTree.parse(report).iter("testcase"))
    except ElementTree.ParseError as error:
        raise ValueError(f"the JUnit report at {report} will not parse") from error


def _last_line(text: Optional[str]) -> str:
    """Return the last line of a traceback, the exception it ended on.

    Args:
        text (Optional[str]): An element's text.

    Returns:
        str: The last non-empty line, or empty when there is none.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1] if lines else ""


def stopped_causes(report: Path) -> list[tuple[str, str]]:
    """Return why pytest ran no case, empty when it ran.

    Args:
        report (Path): The JUnit report the pytest step wrote.

    Returns:
        list: One ``(cause, error)`` pair per reason: the report missing, not
        parsing or holding no case, or each ``collection failure`` and
        ``internal error`` testcase with the exception it ended on.
    """
    try:
        cases = _testcases(report)
    except ValueError as error:
        return [(str(error), "")]
    if not cases:
        return [(f"the JUnit report at {report} holds no case", "")]
    return [
        (f"pytest {problem.get('message')} in {case.get('name', '(unnamed)')}",
         _last_line(problem.text) or str(problem.get("message")))
        for case in cases
        for problem in case.findall("error")
        if problem.get("message") in _SESSION_ERRORS
    ]


def _kind(case: ElementTree.Element) -> tuple[str, str]:
    """Return one testcase's outcome and its message.

    Args:
        case (ElementTree.Element): A ``testcase`` element.

    Returns:
        tuple: ``broken``, ``failed``, ``skipped``, ``passw`` or ``passed``,
        and the message, empty for a pass.
    """
    for tag, kind in _PROBLEMS:
        problem = case.find(tag)
        if problem is not None:
            return kind, str(problem.get("message") or "") or _last_line(problem.text)
    for prop in case.iter("property"):
        if prop.get("name") == "mqc_outcome" and prop.get("value") == "passw":
            return "passw", ""
    return "passed", ""


def _counts(report: Path) -> dict[str, int]:
    """Return how many cases took each outcome.

    Args:
        report (Path): A ran JUnit report.

    Returns:
        dict: ``passed``, ``passw``, ``failed``, ``skipped`` and ``broken`` to counts.
    """
    kinds = [_kind(case)[0] for case in _testcases(report)]
    return {kind: kinds.count(kind) for kind in (*_COUNTED, "broken")}


def outcome_lines(report: Path) -> list[str]:
    """Return a ran report's counts, one labelled count per line.

    Args:
        report (Path): The JUnit report, one :func:`stopped_causes` accepts.

    Returns:
        list[str]: ``total``, ``executed``, ``passed``, ``passw``, ``failed``
        and ``skipped``, then ``broken`` when a case crashed.
    """
    counts = _counts(report)
    lines = [
        f"total: {sum(counts.values())}",
        f"executed: {counts['passed'] + counts['passw'] + counts['failed']}",
        *(f"{kind}: {counts[kind]}" for kind in _COUNTED),
    ]
    if counts["broken"]:
        lines.append(f"broken: {counts['broken']}")
    return lines


def _cell(text: str) -> str:
    """Return text fit for one Markdown table cell.

    Args:
        text (str): The text.

    Returns:
        str: One line, pipes escaped, cut at the message limit.
    """
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= _MESSAGE_LIMIT else f"{flat[:_MESSAGE_LIMIT]}..."


def summary_lines(report: Path) -> list[str]:
    """Render the outcome as the run summary's first section.

    Args:
        report (Path): The JUnit report the pytest step wrote.

    Returns:
        list[str]: Markdown lines: the headline, then the causes of a stopped
        session, or the counts and every case that did not pass.
    """
    causes = stopped_causes(report)
    if causes:
        lines = ["## Outcome: FAILED, pytest stopped before running a case", "",
                 "No case was executed, so nothing was measured.", "",
                 "| Cause | Error |", "|---|---|"]
        return [*lines, *(f"| {_cell(cause)} | {_cell(error) or '-'} |"
                          for cause, error in causes), ""]

    counts = _counts(report)
    executed = counts["passed"] + counts["passw"] + counts["failed"]
    stated = ", ".join(f"{counts[kind]} {kind}" for kind in ("failed", "broken", "passed",
                                                             "passw", "skipped") if counts[kind])
    if counts["failed"] or counts["broken"]:
        verdict = "FAILED"
    elif not executed:
        verdict = "NOTHING EXECUTED"
    else:
        verdict = "PASSED"
    lines = [f"## Outcome: {verdict}, {stated}", "", "```", *outcome_lines(report), "```", ""]
    unpassed = [(case.get("name", "(unnamed)"), *_kind(case)) for case in _testcases(report)]
    unpassed = [row for row in unpassed if row[1] not in ("passed", "passw")]
    if unpassed:
        lines += ["| Case | Outcome | Message |", "|---|---|---|"]
        lines += [f"| {_cell(name)} | {kind} | {_cell(message) or '-'} |"
                  for name, kind, message in unpassed]
        lines.append("")
    return lines


def main(argv: list[str]) -> int:
    """State what the pytest step did.

    Args:
        argv (list[str]): Command line arguments.

    Returns:
        int: ``0`` when pytest ran, ``1`` when it stopped before running a case.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="The JUnit report the pytest step wrote")
    parser.add_argument("--summary", type=Path, help="A Markdown file to append the outcome to")
    arguments = parser.parse_args(argv)

    lines = summary_lines(arguments.report)
    causes = stopped_causes(arguments.report)
    for cause, error in causes:
        print(f"::error::pytest stopped before running a case: {cause}: {error}")
    print("\n".join(lines))
    if arguments.summary is not None:
        with arguments.summary.open("a", encoding=_ENCODING) as page:
            page.write("\n".join([*lines, ""]))
    return 1 if causes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
