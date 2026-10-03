# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Reading the workflow definitions, for the cases that check them.

Extracted 2026-10-03, when the engine-separation cases took
``mqc_uni_workflows.py`` past the thousand-line ceiling and two modules needed
the same readers. **A duplicated reader drifts**, and a case comparing against
a stale copy of a workflow reports about the copy.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, which is the arrangement
``graded_support.py`` already uses.
"""

import re
from pathlib import Path
from typing import Any, Final

import yaml

WORKFLOWS: Final[Path] = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# The markers a graded invocation selects. "sec" is the dangerous one, being a
# substring of section, second, security and secret.
GRADED_MARKERS: Final[tuple[str, ...]] = ("evaluator", "tool", "sec")


def load(name: str) -> dict[str, Any]:
    """Return one workflow definition, parsed.

    Args:
        name (str): The filename inside the workflows directory.

    Returns:
        dict: The parsed document.
    """
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a workflow's jobs.

    Args:
        workflow (dict): The parsed document.

    Returns:
        dict: Job name to its definition.
    """
    return workflow.get("jobs") or {}


def needs(job: dict[str, Any]) -> list[str]:
    """Return what a job declares it needs, however it spells it.

    Args:
        job (dict): The job definition.

    Returns:
        list[str]: The job names, which a single dependency may give as a
        string rather than a list.
    """
    declared = job.get("needs") or []
    return [declared] if isinstance(declared, str) else list(declared)


def run_lines(job: dict[str, Any]) -> list[str]:
    """Return each step's run body with continuations folded.

    **Folded, because a graded invocation spans several lines.** A matcher
    reading raw lines would see the marker on one and the runner on another.

    Args:
        job (dict): The job definition.

    Returns:
        list[str]: One folded body per step that has one.
    """
    folded: list[str] = []
    for step in job.get("steps") or []:
        body = str((step or {}).get("run") or "")
        if body:
            folded.append(re.sub(r"\\\s*\n\s*", " ", body))
    return folded


def selects_a_graded_marker(line: str) -> bool:
    """Report whether a run body invokes pytest selecting a graded marker.

    Args:
        line (str): One step's run body, continuations folded.

    Returns:
        bool: True where a ``-m`` expression names a graded marker as a whole
        word. **A computed expression selects nothing here**, which is
        unchanged: a dispatch passing a marker through an input never carried a
        literal one to match.
    """
    if "pytest" not in line:
        return False
    for quoted, bare in re.findall(r'-m\s+(?:"([^"]*)"|(\S+))', line):
        selected = quoted or bare
        if any(
            re.search(rf"\b{re.escape(marker)}\b", selected)
            for marker in GRADED_MARKERS
        ):
            return True
    return False


def graded_invocations(job: dict[str, Any]) -> list[str]:
    """Return every graded invocation a job makes.

    Args:
        job (dict): The job definition.

    Returns:
        list[str]: The folded run bodies that select a graded marker.
    """
    return [line for line in run_lines(job) if selects_a_graded_marker(line)]
