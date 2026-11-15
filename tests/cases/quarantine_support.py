# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code dropping quarantined cases at collection, so no band runs or counts them.

Created: 2026-11-15
Last updated: 2026-11-15

This file contains ``quarantine_deselection``, which splits collected items
into those kept and those whose corpus case the run's engine has quarantined,
and ``deselect_quarantined_cases``, which ``conftest.py`` calls at collection
to drop the second and report them as deselected.

**A quarantined case is not a skip.** A skip counts as not passed in every
band; a quarantined case has a ticket against it and is being fixed at the
production team's pace, so it is neither run nor counted, at any priority.
Quarantine ends by a manual reset or on expiry, and the case is collected
again from the next run.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by harness ``cmn_verdict_and_cli.md`` section 4.6.14 and
``docs/design/consumer_ci.md`` section 3.12.2.
"""

import logging
from pathlib import Path
from typing import Any, Mapping

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
