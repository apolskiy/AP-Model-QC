# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Where a finding's record lives: the bug file, and the holding list.

Specified by ``docs/design/consumer_ci.md`` section 9.4.8.

**Split from ``findings.py`` on 2026-10-12**, which this subject took to 903
lines against the nine-hundred-line runway ceiling. That module is about
observing a run and merging what it saw; this one is about which file an entry
belongs in once the merge has decided.

**A bug file is what gets filed**, so it carries only what the latest run
reproduced, whatever that finding's failure rate. Everything else waits in
``unconfirmed/`` with its reason: a claim retracted as ours, or one that
stopped reproducing.

**And a run that measured nothing is refused rather than believed.** A
collection error aborts pytest before any case executes and the merge then sees
an empty result: on 2026-10-12 a stale import in one case module emptied all
four bug files in a single command, moving twelve reproducing findings into the
holding list. Recording a finding a run did not see is impossible; retiring one
on an empty result is a silent, total loss, and the asymmetry is why the guard
reads the report rather than the exit status.
"""

import logging
from pathlib import Path
from typing import Any, Final, Optional
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

_REGISTER_ROOT: Final[Path] = Path("config") / "findings"
_HOLDING_ROOT: Final[Path] = _REGISTER_ROOT / "unconfirmed"

# BELOW THIS, A GRADED RUN DID NOT HAPPEN. The suite carries seventy graded
# cases, so a report with fewer than ten means the selection failed rather than
# that the findings resolved.
_MINIMUM_COLLECTED: Final[int] = 10

_UNREPRODUCED: Final[str] = "not_reproduced"


def register_path(engine: str) -> Path:
    """Return the bug file for one engine.

    Args:
        engine (str): The engine.

    Returns:
        Path: The file, which need not exist.
    """
    return _REGISTER_ROOT / f"{engine}.yaml"


def holding_path(engine: str) -> Path:
    """Return where this engine's unfileable findings wait.

    Args:
        engine (str): The engine.

    Returns:
        Path: The holding file, which need not exist.
    """
    return _HOLDING_ROOT / f"{engine}.yaml"


def partition(
    findings: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Split a register into what is fileable and what waits.

    Args:
        findings (dict): Every entry, by case.

    Returns:
        tuple: The fileable entries and the held ones, each by case. **Fileable
        means status open**, which is the only state a vendor can act on.
    """
    fileable = {
        case: entry for case, entry in findings.items()
        if entry.get("status") == "open"
    }
    held = {case: entry for case, entry in findings.items() if case not in fileable}
    return fileable, held


def refuse_empty_run(
    report: Path,
    observed: dict[str, dict[str, Any]],
    held_count: int,
) -> Optional[str]:
    """Return a refusal where this run measured too little to merge.

    **A run that collected nothing is not a run in which nothing reproduced.**
    The guard reads the report rather than the exit status, which a quiet run
    shares between "everything passed" and "nothing was collected".

    Args:
        report (Path): The JUnit XML the run wrote.
        observed (dict): What the run reported, by case.
        held_count (int): How many entries this merge would retire.

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
    if held_count and not observed and len(cases) < _MINIMUM_COLLECTED:
        return (
            f"the run collected {len(cases)} case(s) and reported no failure, "
            f"while {held_count} finding(s) would be retired. A graded suite "
            f"this small means the selection failed"
        )
    return None


def write_register(
    engine: str,
    findings: dict[str, dict[str, Any]],
    renderer: Any,
) -> None:
    """Write the bug file and the holding list from one merged register.

    Args:
        engine (str): The engine whose files to write.
        findings (dict): Every entry, by case.
        renderer (Any): Called as ``renderer(engine, entries, holding=bool)``
            to produce each file's text. **Injected** so this module decides
            placement and ``findings.py`` keeps the format.

    Returns:
        None
    """
    fileable, held = partition(findings)
    register_path(engine).write_text(
        renderer(engine, fileable), encoding="utf-8", newline="\n"
    )
    # AN ABSENT FILE IS HOW THIS PROJECT SAYS "NOTHING HERE" EVERYWHERE ELSE.
    # An empty one invites a reader to wonder what was removed.
    holding = holding_path(engine)
    if held:
        holding.parent.mkdir(parents=True, exist_ok=True)
        holding.write_text(
            renderer(engine, held, holding=True), encoding="utf-8", newline="\n"
        )
    elif holding.is_file():
        holding.unlink()
        logger.info("%s has nothing held, so its holding file is removed", engine)


def to_file(
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the findings to file, and those awaiting measurement.

    Args:
        findings (list): The register's entries.

    Returns:
        tuple: The open findings observed on the newest ``last_observed`` among
        them, and the open findings observed earlier. A withdrawn finding is in
        neither (``consumer_ci.md`` section 9.5.5.1).
    """
    live = [
        entry for entry in findings
        if isinstance(entry, dict) and entry.get("status") != "withdrawn"
    ]
    latest = max((str(entry.get("last_observed") or "") for entry in live), default="")
    filed = [entry for entry in live if str(entry.get("last_observed") or "") == latest]
    return filed, [entry for entry in live if entry not in filed]
