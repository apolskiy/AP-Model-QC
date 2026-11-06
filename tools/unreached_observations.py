# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Recorded observations no replay reaches, because the first pass they escalated from now holds.

Created: 2026-11-06
Last updated: 2026-11-06

This file contains ``unreached_observations``, which lists every engine's
cases holding more recorded observations than the roster's count while every
one of the first observations passes under the current rule, and ``main``,
which prints them.

A run takes the roster's count and two more only when one of those fails. An
observation beyond the first pass therefore belongs to the conditions that
failed, and once those conditions changed and the first pass holds, it is not
evidence: a replay never reads it and a ticket would quote it. Each one listed
is removed, with its judgements under every judge.

Specified by ``docs/design/consumer_ci.md`` section 6.4.7.

Usage::

    python -m tools.unreached_observations
"""

import sys
from pathlib import Path
from typing import Final

from tests.cases.graded_support import case_for, engine_roster
from tools.ticket_recordings import (
    observation_outcomes,
    recorded_judgements,
    recorded_responses,
)
from tools.ticket_report import judged_outcome

_REPLAY: Final[Path] = Path("tests") / "fixtures" / "replay"


def unreached_observations(root: Path) -> list[str]:
    """Return one line per case holding observations beyond a first pass that holds.

    Args:
        root (Path): The repository root.

    Returns:
        list[str]: ``<engine> <task> <rule>: observations <from> to <to> are
        not reached``, sorted. A case whose first pass fails, from a check or
        from its stored judgement against the rubric, is a real escalation and
        is not listed; nor is one whose first-pass judgement is missing, which
        the stale-judgement checks report.
    """
    found: list[str] = []
    for engine, settings in sorted(engine_roster().items()):
        first = max(1, int(getattr(settings, "observations", 0) or 1))
        for rule_dir in sorted((root / _REPLAY / engine).glob("*/*")):
            task, rule = rule_dir.parent.name, rule_dir.name
            count = len(list(rule_dir.glob("*.json")))
            if count > first and _first_pass_holds(root, engine, (task, rule), first):
                found.append(
                    f"{engine} {task} {rule}: observations {first} to {count - 1} are not "
                    f"reached, the first {first} passing"
                )
    return found


def _first_pass_holds(root: Path, engine: str, pair: tuple[str, str], first: int) -> bool:
    """Report whether every one of a case's first observations passes today.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose recordings are read.
        pair (tuple): The task and rule set identifiers.
        first (int): The roster's observation count.

    Returns:
        bool: True where each of the first observations passes its screen,
        assertions and tool checks and, where the rule authors a rubric,
        carries a stored judgement clearing the threshold.
    """
    task, rule = pair
    try:
        rubric = case_for(task, rule).golden_rules.rubric
    except (KeyError, ValueError):
        return False
    recordings = recorded_responses(root, engine, task, rule)[:first]
    checks = observation_outcomes(task, rule, recordings)
    if len(checks) < first or not all(passed for _, passed, _ in checks):
        return False
    if rubric is None:
        return True
    judged = [
        judged_outcome(judgement, rubric)
        for judgement in recorded_judgements(root, engine, task, rule, first)
    ]
    return all(outcome is not None and outcome[0] for outcome in judged)


def main() -> int:
    """Print every case holding observations no replay reaches.

    Returns:
        int: ``1`` where any is found, ``0`` where none is.
    """
    found = unreached_observations(Path(__file__).resolve().parents[1])
    for line in found:
        print(line)
    print(f"{len(found)} case(s) hold observations beyond a first pass that holds")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
