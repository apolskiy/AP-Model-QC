# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Builders the ticket reproduction cases share, selecting a case by its property.

Created: 2026-11-05
Last updated: 2026-11-05

This file contains :func:`instructed_section`, which finds the first graded
case whose task carries a system instruction and whose recording exists on an
engine, and returns the ticket section ``tools.ticket_report`` writes for it
from a minimal register entry.

``mqc_uni_ticket_reproduction.py`` reads it. **The case is found by its
property, never named**, because which cases hold recordings moves with every
re-recording, and a named one turns a measurement into a broken precondition.
Not collected, the filename carrying no ``mqc_`` prefix.

Specified by ``docs/design/consumer_ci.md`` section 9.5.5.13.
"""

import json
from pathlib import Path
from typing import Any, Final, Optional

from tests.cases.suite_support import case_rules_from_suite
from tools.ticket_recordings import recorded_request
from tools.ticket_report import finding_section, load_tasks

ROOT: Final[Path] = Path(__file__).resolve().parents[2]


def instructed_section(
    engine: str, fields: Optional[dict[str, Any]] = None
) -> tuple[str, str, str]:
    """Return a ticket section for a case whose recording carries its system instruction.

    Args:
        engine (str): The engine whose recordings to read.
        fields (Optional[dict]): Register fields the entry carries beyond the
            minimal ones.

    Returns:
        tuple: The case name, the task's system instruction, and the section's
        Markdown. Empty strings where no such case is recorded on the engine.
    """
    tasks = load_tasks(ROOT)
    pairs = case_rules_from_suite(ROOT)
    for case, (task_id, rule_id) in sorted(pairs.items()):
        instruction = str((tasks.get(task_id) or {}).get("system_instruction") or "").strip()
        request = recorded_request(ROOT, engine, task_id, rule_id)
        # THE RECORDING MUST CARRY THE INSTRUCTION, not only the task. A task
        # given one after it was recorded is held for re-recording, and its
        # ticket rightly shows the call as it was made.
        if not instruction or request is None or (
            instruction.splitlines()[0] not in json.dumps(request, ensure_ascii=False)
        ):
            continue
        entry = {"case": case, "taxonomy_code": "QC_LLM_INSTRUCTION_VIOLATION",
                 "observed_model": "a-served-model-2026-01-01", **(fields or {})}
        return case, instruction, "\n".join(finding_section(ROOT, engine, entry, pairs, tasks))
    return "", "", ""
