# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Waits for an engine's gate at one commit before a regression run resolves its harness.

Created: 2026-11-18
Last updated: 2026-11-18

This file contains ``GateWait``, what the wait found, ``await_gate``, which
polls the runs of one gate workflow at one commit until none is queued or in
progress, and ``main``, the entry point the ``resolve`` job of
``evaluate-engine.yml`` runs first.

A regression run calls it before the harness is resolved and before anything
is spent. Its result never stops the run: it exits 0 whatever it found, writes
``gate_conclusion`` for the job to export, and adds a line to the run summary.
The gate's own conclusion is returned once it concludes; ``unfinished`` where a
run was still queued or in progress at the cut-off, and ``absent`` where no run
of the gate was listed by then.

The run query and the wait terms are ``tools.harness_pin``'s.

Specified by ``docs/design/consumer_ci.md`` section 7.9.6.
"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Optional

from tools import harness_pin

logger = logging.getLogger(__name__)

# THE OWNER'S CUT-OFF, 2026-11-18, and the interval between checks.
_TIMEOUT_MINUTES: Final[float] = 30.0
_INTERVAL_SEC: Final[float] = 30.0

# WHAT THE WAIT RETURNS WHERE THE GATE NEVER CONCLUDED.
UNFINISHED: Final[str] = "unfinished"
ABSENT: Final[str] = "absent"
_COMPLETED: Final[str] = "completed"


@dataclass(frozen=True)
class GateWait:
    """What the wait found.

    Attributes:
        conclusion (str): The gate's conclusion, or ``unfinished`` or ``absent``.
        waited_sec (float): How long the wait's clock says it waited.
    """

    conclusion: str
    waited_sec: float


def _gate_runs(runs: list[dict[str, Any]], workflow: str, commit: str) -> list[dict[str, Any]]:
    """Return the runs of one workflow at one commit.

    Args:
        runs (list): Runs as the GitHub API lists them.
        workflow (str): The workflow file name.
        commit (str): The commit.

    Returns:
        list[dict]: The matching runs, newest first.
    """
    matching = [
        run for run in runs
        if str(run.get("path", "")).rsplit("/", 1)[-1] == workflow
        and str(run.get("head_sha", "")) == commit
    ]
    return sorted(matching, key=lambda run: str(run.get("created_at", "")), reverse=True)


def await_gate(
    fetch: Callable[[str], list[dict[str, Any]]],
    workflow: str,
    commit: str,
    policy: harness_pin.WaitPolicy,
) -> GateWait:
    """Wait while the gate at a commit is unlisted, queued or in progress.

    Design: ``consumer_ci.md`` section 7.9.6.

    Args:
        fetch (Callable): Lists the workflow runs at a commit.
        workflow (str): The gate workflow file.
        commit (str): The commit the regression run measures.
        policy (harness_pin.WaitPolicy): The cut-off, the interval and the clock.

    Returns:
        GateWait: The newest run's conclusion once none is pending, or
        ``unfinished`` or ``absent`` at the cut-off. The listing is read before
        the cut-off is compared, so a gate concluding at the cut-off is read.
    """
    started = policy.monotonic()
    while True:
        runs = _gate_runs(fetch(commit), workflow, commit)
        waited = policy.monotonic() - started
        if runs and all(str(run.get("status", "")) == _COMPLETED for run in runs):
            return GateWait(str(runs[0].get("conclusion") or ""), waited)
        if waited >= policy.timeout_sec:
            return GateWait(UNFINISHED if runs else ABSENT, waited)
        policy.delay(policy.interval_sec)


def _summary_line(workflow: str, commit: str, found: GateWait) -> str:
    """Return the run summary's line for what the wait found.

    Args:
        workflow (str): The gate workflow file.
        commit (str): The commit.
        found (GateWait): What the wait found.

    Returns:
        str: One line, naming the gate, the commit and the outcome.
    """
    minutes = found.waited_sec / 60.0
    if found.conclusion == UNFINISHED:
        outcome = f"had not finished after {minutes:.0f} minutes; the run proceeds"
    elif found.conclusion == ABSENT:
        outcome = f"had no run listed after {minutes:.0f} minutes; the run proceeds"
    else:
        outcome = f"concluded {found.conclusion} after a wait of {minutes:.1f} minutes"
    return f"{workflow} at {commit[:12]} {outcome}"


def _append(path: str, text: str) -> None:
    """Append text to a file a workflow reads, where one is named.

    Args:
        path (str): The file, or empty for none.
        text (str): What to append.

    Returns:
        None
    """
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(text)


def main(
    argv: Optional[list[str]] = None,
    *,
    fetch: Optional[Callable[[str], list[dict[str, Any]]]] = None,
    policy: Optional[harness_pin.WaitPolicy] = None,
) -> int:
    """Wait for the gate, write its conclusion and a summary line, and exit 0.

    Args:
        argv (Optional[list[str]]): The arguments, ``sys.argv`` where omitted.
        fetch (Optional[Callable]): Lists runs at a commit; the GitHub API
            where omitted.
        policy (Optional[harness_pin.WaitPolicy]): The wait terms; the
            arguments' cut-off and interval on the real clock where omitted.

    Returns:
        int: 0, whatever the gate concluded.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--timeout-minutes", type=float, default=_TIMEOUT_MINUTES)
    parser.add_argument("--interval-seconds", type=float, default=_INTERVAL_SEC)
    parser.add_argument("--output", default=os.environ.get("GITHUB_OUTPUT", ""))
    parser.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    parsed = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    lister = fetch or (
        lambda commit: harness_pin.fetch_runs(parsed.repository, commit, token)
    )
    terms = policy or harness_pin.WaitPolicy(
        timeout_sec=parsed.timeout_minutes * 60.0, interval_sec=parsed.interval_seconds,
    )
    found = await_gate(lister, parsed.workflow, parsed.commit, terms)
    line = _summary_line(parsed.workflow, parsed.commit, found)
    logger.info(line)
    print(line)
    _append(parsed.output, f"gate_conclusion={found.conclusion}\n")
    _append(parsed.summary, f"## Gate\n\n{line}\n")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
