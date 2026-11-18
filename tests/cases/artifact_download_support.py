# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading each workflow's artifact downloads and uploads, for the cases checking them.

Created: 2026-11-18
Last updated: 2026-11-18

This file contains ``artifact_names``, which reads an artifact name or pattern
as the names it can take, each ``${{ }}`` expression a placeholder and a whole
expression the ``format()`` strings it chooses between; ``fallible_downloads``,
which lists each download step without ``continue-on-error: true``;
``unproduced_downloads``, which lists each download naming an artifact no upload
in its workflow, or in a workflow it calls, writes; ``downloads``, which counts
a workflow's download steps; and ``workflow_files``, every workflow in this
repository.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately.

Specified by ``docs/design/consumer_ci.md`` section 3.12.1.3.
"""

import re
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Final

import yaml

from tests.cases.workflow_support import WORKFLOWS, jobs

DOWNLOAD: Final[str] = "actions/download-artifact"
UPLOAD: Final[str] = "actions/upload-artifact"

# WHAT AN EXPRESSION READS AS, so two names differing only in what a run
# substitutes compare equal and a name missing a part does not.
PLACEHOLDER: Final[str] = "<expr>"

_EXPRESSION: Final[re.Pattern[str]] = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)
_FORMAT: Final[re.Pattern[str]] = re.compile(r"format\(\s*'([^']*)'")
_ARGUMENT: Final[re.Pattern[str]] = re.compile(r"\{\d+\}")
_LOCAL_WORKFLOW: Final[str] = "./.github/workflows/"


def artifact_names(value: str) -> list[str]:
    """Return the names an artifact name or pattern can take, expressions as placeholders.

    Args:
        value (str): The ``name:`` or ``pattern:`` as the workflow writes it.

    Returns:
        list[str]: One name, or, where the whole value is one expression, each
        ``format()`` string it chooses between, or the placeholder where it
        holds none.
    """
    text = " ".join(str(value).split())
    if _EXPRESSION.fullmatch(text):
        chosen = _FORMAT.findall(text)
        return [_ARGUMENT.sub(PLACEHOLDER, found) for found in chosen] or [PLACEHOLDER]
    return [_EXPRESSION.sub(PLACEHOLDER, text)]


def _steps(workflow: dict[str, Any], action: str) -> list[tuple[str, dict[str, Any]]]:
    """Return each step using an action, with the job holding it.

    Args:
        workflow (dict): The parsed document.
        action (str): The action's name, without its version.

    Returns:
        list[tuple]: The job name and the step.
    """
    return [
        (name, entry)
        for name, job in jobs(workflow).items()
        for entry in job.get("steps") or []
        if str(entry.get("uses", "")).split("@", 1)[0] == action
    ]


def downloads(workflow: dict[str, Any]) -> int:
    """Return how many download steps a workflow holds.

    Args:
        workflow (dict): The parsed document.

    Returns:
        int: The count.
    """
    return len(_steps(workflow, DOWNLOAD))


def fallible_downloads(workflow: dict[str, Any]) -> list[str]:
    """Return each download step that fails its job when the artifact is not found.

    Args:
        workflow (dict): The parsed document.

    Returns:
        list[str]: The job and the artifact, for each step without
        ``continue-on-error: true``.
    """
    fallible: list[str] = []
    for job, entry in _steps(workflow, DOWNLOAD):
        if entry.get("continue-on-error") is True:
            continue
        supplied = entry.get("with") or {}
        fallible.append(f"{job} downloads {supplied.get('name') or supplied.get('pattern')}")
    return fallible


def _uploaded(workflow: dict[str, Any], called: dict[str, dict[str, Any]]) -> list[str]:
    """Return every name an upload in the workflow, or in a workflow it calls, writes.

    Args:
        workflow (dict): The parsed document.
        called (dict): Each local workflow by filename, for the jobs that call one.

    Returns:
        list[str]: The names, expressions as placeholders.
    """
    sources = [workflow] + [
        called[str(job.get("uses"))[len(_LOCAL_WORKFLOW):]]
        for job in jobs(workflow).values()
        if str(job.get("uses", "")).startswith(_LOCAL_WORKFLOW)
        and str(job.get("uses"))[len(_LOCAL_WORKFLOW):] in called
    ]
    return [
        name
        for source in sources
        for _, entry in _steps(source, UPLOAD)
        for name in artifact_names(str((entry.get("with") or {}).get("name", "")))
    ]


def unproduced_downloads(
    workflow: dict[str, Any], called: dict[str, dict[str, Any]],
) -> list[str]:
    """Return each download naming an artifact no upload in its workflow writes.

    Args:
        workflow (dict): The parsed document.
        called (dict): Each local workflow by filename, for the jobs that call one.

    Returns:
        list[str]: The job and the name or pattern, for each download a run of
        this workflow could not find.
    """
    uploaded = _uploaded(workflow, called)
    unproduced: list[str] = []
    for job, entry in _steps(workflow, DOWNLOAD):
        supplied = entry.get("with") or {}
        if "name" in supplied:
            wanted = artifact_names(str(supplied["name"]))
            missing = [name for name in wanted if name not in uploaded]
        elif "pattern" in supplied:
            wanted = artifact_names(str(supplied["pattern"]))
            missing = [pattern for pattern in wanted
                       if not any(fnmatchcase(name, pattern) for name in uploaded)]
        else:
            missing = []
        unproduced.extend(f"{job} downloads {name}, which no upload writes" for name in missing)
    return unproduced


def workflow_files() -> dict[str, dict[str, Any]]:
    """Return every workflow in this repository, parsed, by filename.

    Returns:
        dict: Filename to its parsed document.
    """
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(Path(WORKFLOWS).glob("*.yml"))
    }
