# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code dropping quarantined cases at collection, so no band runs or counts them.

Created: 2026-11-15
Last updated: 2026-11-15

This file contains ``quarantine_deselection``, which splits collected items
into those kept and those whose corpus case the run's engine has quarantined,
``deselect_quarantined_cases``, which ``conftest.py`` calls at collection
to drop the second and report them as deselected; and, for the cases,
``write_quarantine_file``, which writes an engine's file, ``file_entry``, one
entry of it, and ``dropped_names``, what collection drops for a held set.

**A quarantined case is not a skip.** A skip counts as not passed in every
band; a quarantined case has a ticket against it and is being fixed at the
production team's pace, so it is neither run nor counted, at any priority.
Only an entry in force holds its case out: quarantine ends on removal, on
expiry of its window, or on a model change where the entry says so, and the
case is collected again from the next run.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by harness ``cmn_verdict_and_cli.md`` section 4.6.14 and
``docs/design/consumer_ci.md`` section 3.12.2.
"""

import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import yaml

from ingestion.cases import build_case_id

from tests.cases import suite_support
from tests.cases.graded_support import quarantined_cases

logger = logging.getLogger(__name__)


def quarantine_deselection(
    items: list[Any],
    pairs: Mapping[str, tuple[str, str]],
    quarantined: frozenset[str],
) -> tuple[list[Any], list[Any]]:
    """Split the items into those kept and those whose corpus case is quarantined.

    Args:
        items (list): The collected items, each read for ``originalname`` or
            ``name``.
        pairs (Mapping): Case name to the task and rule it dispatches, as
            ``suite_support.case_rules_from_suite`` returns it.
        quarantined (frozenset[str]): The quarantined corpus case identifiers.

    Returns:
        tuple: The items kept and the items dropped, each in collection order.
    """
    kept: list[Any] = []
    dropped: list[Any] = []
    for item in items:
        name = str(getattr(item, "originalname", None) or getattr(item, "name", ""))
        pair = pairs.get(name)
        if pair is not None and build_case_id(*pair) in quarantined:
            dropped.append(item)
        else:
            kept.append(item)
    return kept, dropped


def write_quarantine_file(
    config_dir: Path, engine: str, entries: list[dict[str, Any]]
) -> Path:
    """Write ``quarantine/<engine>.yaml`` under a config directory, for a case to read.

    Args:
        config_dir (Path): The config directory to write under.
        engine (str): The engine the file is for.
        entries (list): The entries, as the file holds them.

    Returns:
        Path: The file written.
    """
    target = config_dir / "quarantine" / f"{engine}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump({"quarantine": entries}, sort_keys=False),
        encoding="utf-8", newline="\n",
    )
    return target


def file_entry(
    case_id: str, quarantined_on: date, observed_model: str, **fields: object
) -> dict[str, object]:
    """Return one quarantine file entry carrying a ticket.

    Args:
        case_id (str): The composed case identifier.
        quarantined_on (date): The date the entry was last stamped.
        observed_model (str): The model it was observed against.
        **fields (object): Fields overriding the defaults.

    Returns:
        dict: The entry as the file holds it.
    """
    return {
        "case_id": case_id, "reason": "known failure",
        "quarantined_on": quarantined_on.isoformat(),
        "observed_model": observed_model, "ticket": "MQC-41", **fields,
    }


def dropped_names(pairs: Mapping[str, tuple[str, str]], held: frozenset[str]) -> list[str]:
    """Return the case names collection drops for a held set, one item per name.

    Args:
        pairs (Mapping): Case name to the task and rule it dispatches.
        held (frozenset[str]): The case identifiers held out.

    Returns:
        list[str]: The names dropped, in the mapping's order.
    """
    items = [SimpleNamespace(name=name) for name in pairs]
    _, dropped = quarantine_deselection(items, pairs, held)
    return [item.name for item in dropped]


def deselect_quarantined_cases(config: Any, items: list[Any], root: Path) -> int:
    """Drop every collected case the run's engine has quarantined.

    Reads the suite only where the engine has a quarantined case, so a run
    with none pays nothing for it.

    Args:
        config (Any): pytest's configuration, read for ``--engine`` and
            carrying the deselection hook.
        items (list): The collected items, changed in place.
        root (Path): This repository's root.

    Returns:
        int: How many cases were dropped.
    """
    quarantined = quarantined_cases(config)
    if not quarantined:
        return 0
    kept, dropped = quarantine_deselection(
        items, suite_support.case_rules_from_suite(root), quarantined,
    )
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
        logger.info(
            "Quarantine: %d case(s) deselected, each with a ticket against it: %s",
            len(dropped), ", ".join(str(getattr(item, "name", "")) for item in dropped),
        )
    return len(dropped)
