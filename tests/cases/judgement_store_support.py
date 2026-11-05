# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Reader of the stored judgements that were made without the system instruction.

Created: 2026-11-05
Last updated: 2026-11-05

This file contains :func:`judgements_without_instruction`, which counts the
stored judgements of every shipped task carrying a system instruction and
names those whose judge prompt does not carry that instruction in its own
data field. ``mqc_uni_judge_material.py`` calls it.

**Not collected**, as the filename carries no ``mqc_`` prefix: a case module
holds only cases (harness ``harness_test_taxonomy.md`` section 13).

Specified by ``docs/design/consumer_ci.md`` section 6.4.4.
"""

import json
from typing import Final

from tests.cases.graded_support import FIXTURE_ROOT, repository_root, shipped_corpus

# How the harness opens the data field holding the system instruction in a
# judge prompt (harness tier3_evaluation.md section 3.1.2).
_INSTRUCTION_FIELD: Final[str] = "<data field=system_instruction>"


def judgements_without_instruction() -> tuple[int, list[str]]:
    """Return how many stored judgements of instructed tasks there are, and which lack it.

    A judgement lacks the instruction where its prompt carries no
    ``system_instruction`` data field holding the task's instruction word for
    word, and such a judgement is invalid.

    Returns:
        tuple: The number of stored judgements of tasks carrying a system
        instruction, then the store-relative paths of those lacking it.
    """
    tasks, _ = shipped_corpus()
    instructed = {
        task.task_id: task.system_instruction.strip()
        for task in tasks if task.system_instruction
    }
    store = repository_root() / FIXTURE_ROOT / "judgements"
    judged = [
        path for path in sorted(store.glob("*/*/*/*/*.json"))
        if path.parts[-3] in instructed
    ]
    lacking = []
    for path in judged:
        prompt = json.loads(path.read_text(encoding="utf-8")).get("prompt", "")
        opened = prompt.find(_INSTRUCTION_FIELD)
        if opened < 0 or instructed[path.parts[-3]] not in prompt[opened:]:
            lacking.append(path.relative_to(store).as_posix())
    return len(judged), lacking
