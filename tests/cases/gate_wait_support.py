# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Helpers for the cases over the wait a regression run makes for its engine's gate.

Created: 2026-11-18
Last updated: 2026-11-18

This file contains the simulated workflow runs, a wait driven by an injected
clock, a run of the tool's entry point that captures what it writes, and the
reading of the ``resolve`` job's steps. No helper calls the GitHub API.

Specified by ``docs/design/consumer_ci.md`` section 7.9.6.
"""

from pathlib import Path
from typing import Any, Callable, Final

from tools import gate_wait, harness_pin
from tests.cases.workflow_support import jobs, load

# THE ENGINE, ITS GATE AND THE COMMIT A REGRESSION RUN MEASURES. Section 7.9.6.
ENGINE: Final[str] = "claude"
GATE: Final[str] = f"gate-{ENGINE}.yml"
COMMIT: Final[str] = "a" * 40
OTHER_COMMIT: Final[str] = "b" * 40

# THE OWNER'S CUT-OFF, AND THE INTERVAL BETWEEN CHECKS, in seconds.
TIMEOUT_SEC: Final[float] = 30 * 60.0
INTERVAL_SEC: Final[float] = 30.0

# THE JOB THAT WAITS, AND THE TOOL IT RUNS.
RESOLVE_JOB: Final[str] = "resolve"
WAIT_TOOL: Final[str] = "tools.gate_wait"
PIN_TOOL: Final[str] = "tools.harness_pin"


def gate_run(
    status: str, conclusion: str = "", *, workflow: str = GATE, commit: str = COMMIT,
    created: str = "2026-11-18T10:00:00Z",
) -> dict[str, Any]:
    """Return one workflow run as the GitHub API lists it.

    Args:
        status (str): ``queued``, ``in_progress``, ``completed`` and the like.
        conclusion (str): The conclusion of a completed run, empty otherwise.
        workflow (str): The workflow file the run is of.
        commit (str): The commit it ran at.
        created (str): When it was created, ISO 8601.

    Returns:
        dict: The fields the wait reads.
    """
    return {
        "path": f".github/workflows/{workflow}",
        "head_sha": commit,
        "status": status,
        "conclusion": conclusion or None,
        "created_at": created,
    }


def simulated_wait(
    sequence: list[list[dict[str, Any]]], timeout: float = TIMEOUT_SEC,
) -> tuple[Any, list[str], float]:
    """Run the wait over one listing of runs per check, the last repeated.

    Args:
        sequence (list): The runs listed at each check.
        timeout (float): The wait's cut-off.

    Returns:
        tuple: What the wait returned, each commit it asked about, and how long
        its clock says it waited.
    """
    remaining = list(sequence)
    asked: list[str] = []
    now = [0.0]

    def fetch(commit: str) -> list[dict[str, Any]]:
        asked.append(commit)
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    result = gate_wait.await_gate(
        fetch, GATE, COMMIT, harness_pin.WaitPolicy(
            timeout_sec=timeout, interval_sec=INTERVAL_SEC,
            monotonic=lambda: now[0],
            delay=lambda seconds: now.__setitem__(0, now[0] + seconds),
        ),
    )
    return result, asked, now[0]


def run_tool(
    directory: Path, runs: list[dict[str, Any]],
) -> tuple[int, str, str]:
    """Run the tool's entry point over one listing, capturing its output and summary.

    Args:
        directory (Path): Where the output and summary files are written.
        runs (list): The runs every check lists.

    Returns:
        tuple: The exit status, the output file's text and the summary's text.
    """
    output = directory / "output.txt"
    summary = directory / "summary.md"
    fetch: Callable[[str], list[dict[str, Any]]] = lambda _commit: runs
    status = gate_wait.main(
        [
            "--repository", "apolskiy/AP-Model-QC", "--workflow", GATE,
            "--commit", COMMIT, "--output", str(output), "--summary", str(summary),
        ],
        fetch=fetch,
        policy=harness_pin.WaitPolicy(
            timeout_sec=TIMEOUT_SEC, interval_sec=INTERVAL_SEC,
            monotonic=lambda: 0.0, delay=lambda _seconds: None,
        ),
    )
    return status, _text_of(output), _text_of(summary)


def _text_of(path: Path) -> str:
    """Return a file's text, or empty where the tool wrote none.

    Args:
        path (Path): The file.

    Returns:
        str: Its text.
    """
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def resolve_steps(workflow: str) -> list[dict[str, Any]]:
    """Return the steps of a workflow's ``resolve`` job.

    Args:
        workflow (str): The workflow file.

    Returns:
        list[dict]: Its steps in order, empty where it has no such job.
    """
    return list(jobs(load(workflow)).get(RESOLVE_JOB, {}).get("steps") or [])


def step_index(steps: list[dict[str, Any]], tool: str) -> int:
    """Return the position of the first step running a tool, or -1.

    Args:
        steps (list): A job's steps.
        tool (str): The module a step runs with ``python -m``.

    Returns:
        int: Its index, or -1 where no step runs it.
    """
    for index, entry in enumerate(steps):
        if f"python -m {tool}" in str(entry.get("run", "")):
            return index
    return -1


def conditions(workflow: str) -> list[str]:
    """Return every job and step condition in a workflow.

    Args:
        workflow (str): The workflow file.

    Returns:
        list[str]: Each ``if`` as written.
    """
    found: list[str] = []
    for job in jobs(load(workflow)).values():
        if "if" in job:
            found.append(str(job["if"]))
        found.extend(str(entry["if"]) for entry in job.get("steps") or [] if "if" in entry)
    return found
