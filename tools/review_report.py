# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The review report, which writes the withdrawn findings that are failing again.

Created: 2026-10-30
Last updated: 2026-10-30

This file contains ``review_page_for``, which builds one engine's page of
withdrawn findings the latest run reproduced, ``review_summary``, which writes
the temporary summary each one opens with, and ``main``, which writes a page per
engine and one ticket per returned finding under ``reports/tickets/review/``.

It runs after ``tools.findings`` has merged a run and after
``tools.ticket_report`` has written the filed tickets. Each ticket it writes
carries the same four parts a filed one does, assembled by
``ticket_report.finding_section``, and none of them reaches ``FILING.md``: a
withdrawn finding that reproduces is evidence for a decision rather than
something to send a vendor.

Specified by ``docs/design/consumer_ci.md`` section 9.5.5.12.

**It is a module of its own because the filing set and the review set are two
subjects**, and ``ticket_report.py`` reached the thousand-line hard limit on the
change that added this one (``code-style.md`` section 5.1).

Usage::

    python -m tools.review_report
    python -m tools.review_report --engine claude
"""

import sys
from pathlib import Path
from typing import Any, Final, Optional

import yaml

from tests.cases.graded_support import engine_roster
from tests.cases.suite_support import case_rules_from_suite
from tools.ticket_files import (
    GENERATED_MARK,
    page_name,
    report_arguments,
    write_tickets,
)
from tools.ticket_report import finding_section, load_tasks

_DEFAULT_OUT: Final[Path] = Path("reports") / "tickets" / "review"


def review_summary(entry: dict[str, Any]) -> list[str]:
    """Return the temporary summary a returned finding carries above its evidence.

    Args:
        entry (dict): The holding list entry.

    Returns:
        list[str]: Markdown lines naming the withdrawal, its date, the reason
        recorded at the time and the date it was observed again. **Temporary by
        design**: it states an open question rather than a conclusion, and it
        goes when the question is answered. It carries no heading, since
        :func:`~tools.ticket_report.finding_section` opens with the case as one
        and a second above it reads as two findings.
    """
    reason = str(entry.get("withdrawn_reason") or entry.get("held_reason") or "")
    when = str(entry.get("withdrawn_on") or entry.get("held_on") or "")
    return [
        f"**Temporary summary, pending a ruling.** This finding was "
        f"{entry.get('status', 'withdrawn')} on {when} and the recordings of "
        f"{entry.get('reproduced_on', '')} fail it again. The reason recorded "
        f"at the time was: {reason}",
        "",
    ]


def review_page_for(
    root: Path, engine: str
) -> tuple[str, list[tuple[dict[str, Any], list[str]]]]:
    """Return the review page for one engine, and each returned finding's section.

    Args:
        root (Path): The repository root.
        engine (str): The engine to report.

    Returns:
        tuple: Markdown with one section per returned finding, and each finding
        paired with its section. A withdrawn finding the latest run did not
        reproduce is in neither, so nothing carries a ticket for it.
    """
    register = root / "config" / "findings" / "unconfirmed" / f"{engine}.yaml"
    if not register.is_file():
        return "", []

    payload = yaml.safe_load(register.read_text(encoding="utf-8")) or {}
    held = [entry for entry in payload.get("findings") or [] if isinstance(entry, dict)]
    # THE NEWEST REPRODUCTION ONLY. An entry carrying an older date reproduced
    # on a run that is no longer the measurement, and a ticket for it would be
    # evidence about a corpus this repository has replaced.
    latest = max((str(entry.get("reproduced_on") or "") for entry in held), default="")
    returned = [entry for entry in held
                if latest and str(entry.get("reproduced_on") or "") == latest]
    if not returned:
        return "", []

    pairs = case_rules_from_suite(root)
    tasks = load_tasks(root)
    sections = [(entry, review_summary(entry)
                 + finding_section(root, engine, entry, pairs, tasks))
                for entry in returned]
    out = [
        GENERATED_MARK,
        "",
        f"# Withdrawn findings against `{engine}` that reproduce",
        "",
        f"**{len(returned)} finding(s), observed again on {latest}.** None is "
        f"filed and none is counted in `FILING.md`: each was retracted as this "
        f"instrument's own defect and has started failing again.",
        "",
        "**The ruling each one needs is the same**: either the assertion was "
        "repaired since the withdrawal and now fires correctly, or the same "
        "false positive has come back. The evidence for that reading is below, "
        "the prompt as sent and every recorded response, the passing ones "
        "included.",
        "",
        "---",
        "",
    ]
    for _, lines in sections:
        out.extend(lines)
    return "\n".join(out), sections


def main(argv: Optional[list[str]] = None) -> int:
    """Write one review page per engine, and one ticket per returned finding.

    Args:
        argv (Optional[list]): Arguments, or None to read from the command line.

    Returns:
        int: Zero on success.
    """
    parsed = report_arguments(__doc__, _DEFAULT_OUT, argv)
    root = Path(__file__).resolve().parents[1]
    # THE ROSTER IS READ, NOT RESTATED. It comes from the installed harness's
    # `config/engines.yaml`, which is the one place that says which engines
    # exist (`framework-rules.md` section 4.1).
    chosen = (parsed.engine,) if parsed.engine else tuple(engine_roster())

    for engine in chosen:
        page, returned = review_page_for(root, engine)
        # PRUNED WHETHER OR NOT ANYTHING RETURNED, so a finding that stopped
        # reproducing loses the review ticket it had: a ticket nothing
        # reproduces is evidence about a measurement that no longer exists.
        written = write_tickets(parsed.out_dir / engine, engine, returned)
        page_path = parsed.out_dir / page_name(engine)
        if not returned:
            if page_path.is_file():
                page_path.unlink()
                print(f"{page_path}: removed, nothing withdrawn reproduces")
            # AND THE DIRECTORY, WHERE IT IS EMPTY. An empty directory reads as
            # an engine with findings under review and it has none
            # (section 9.5.5.11 applied to the review set).
            engine_dir = parsed.out_dir / engine
            if engine_dir.is_dir() and not any(engine_dir.iterdir()):
                engine_dir.rmdir()
            continue
        page_path.write_text(page, encoding="utf-8", newline="\n")
        print(f"{page_path}: written, with {len(written)} review ticket(s) in "
              f"review/{engine}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
