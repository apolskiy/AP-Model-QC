# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The findings file writer, which writes each engine's bug file and chooses what is filed.

Created: 2026-10-12
Last updated: 2026-11-06

This file contains ``register_path``, which names an engine's bug file,
``to_file``, which splits a register into what is filed and what awaits
measurement, ``refuse_empty_run``, which refuses a merge from a run that
measured too little, and ``write_register``, which writes the bug file from one
merged register.

``tools.findings`` calls it after reading a run, to refuse or write, and
``tools.ticket_report`` calls ``to_file`` to choose the findings that get a
ticket.

Specified by ``docs/design/consumer_ci.md`` section 9.4.11.

**Split from ``findings.py`` on 2026-10-12**, which this subject took to 903
lines against the nine-hundred-line runway ceiling.

**One file per engine.** It holds the open findings and those a live run
resolved upstream; only the open ones are filed.

**And a run that measured nothing is refused rather than believed.** A
collection error aborts pytest before any case executes and the merge then sees
an empty result: on 2026-10-12 a stale import in one case module emptied all
four bug files in a single command. Recording a finding a run did not see is
impossible; retiring one on an empty result is a silent, total loss, and the
asymmetry is why the guard reads the report rather than the exit status.
"""

from pathlib import Path
from typing import Any, Final, Optional
from xml.etree import ElementTree

_REGISTER_ROOT: Final[Path] = Path("config") / "findings"

# BELOW THIS, A GRADED RUN DID NOT HAPPEN. The suite carries seventy graded
# cases, so a report with fewer than ten means the selection failed rather than
# that the findings resolved.
_MINIMUM_COLLECTED: Final[int] = 10


def register_path(engine: str) -> Path:
    """Return the bug file for one engine.

    Args:
        engine (str): The engine.

    Returns:
        Path: The file, which need not exist.
    """
    return _REGISTER_ROOT / f"{engine}.yaml"


def refuse_empty_run(
    report: Path,
    observed: dict[str, dict[str, Any]],
    retired_count: int,
) -> Optional[str]:
    """Return a refusal where this run measured too little to merge.

    **A run that collected nothing is not a run in which nothing reproduced.**
    The guard reads the report rather than the exit status, which a quiet run
    shares between "everything passed" and "nothing was collected".

    Args:
        report (Path): The JUnit XML the run wrote.
        observed (dict): What the run reported, by case.
        retired_count (int): How many entries this merge would remove or
            resolve upstream.

    Returns:
        Optional[str]: The reason to refuse, or None where the run may be
        merged. **Only a retiring merge is guarded**, because recording a new
        finding from a small run is self-limiting and losing an existing one is
        not.
    """
    try:
        root = ElementTree.parse(report).getroot()
    except (OSError, ElementTree.ParseError) as error:
        return f"the run wrote no readable report: {error}"
    cases = list(root.iter("testcase"))
    errors = [case for case in cases if case.find("error") is not None]
    if errors:
        names = ", ".join(sorted(case.get("name", "?") for case in errors)[:3])
        return (
            f"{len(errors)} collection or setup error(s) in the run ({names}). "
            f"A run that could not collect is not a run in which nothing "
            f"reproduced"
        )
    if retired_count and not observed and len(cases) < _MINIMUM_COLLECTED:
        return (
            f"the run collected {len(cases)} case(s) and reported no failure, "
            f"while {retired_count} finding(s) would be retired. A graded suite "
            f"this small means the selection failed"
        )
    return None


def write_register(
    engine: str,
    findings: dict[str, dict[str, Any]],
    renderer: Any,
) -> None:
    """Write the bug file from one merged register.

    Args:
        engine (str): The engine whose file to write.
        findings (dict): Every entry, by case, open and resolved alike.
        renderer (Any): Called as ``renderer(engine, entries)`` to produce the
            file's text. **Injected** so ``findings.py`` keeps the format.

    Returns:
        None
    """
    register_path(engine).write_text(
        renderer(engine, findings), encoding="utf-8", newline="\n"
    )

def to_file(
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the findings to file, and those awaiting measurement.

    Args:
        findings (list): The register's entries.

    Returns:
        tuple: The open findings observed on the newest ``last_observed`` among
        them, and the open findings observed earlier. A finding resolved
        upstream is in neither (``consumer_ci.md`` sections 9.5.5.1 and 9.4.11).
    """
    live = [
        entry for entry in findings
        if isinstance(entry, dict) and entry.get("status", "open") == "open"
    ]
    latest = max((str(entry.get("last_observed") or "") for entry in live), default="")
    filed = [entry for entry in live if str(entry.get("last_observed") or "") == latest]
    return filed, [entry for entry in live if entry not in filed]
