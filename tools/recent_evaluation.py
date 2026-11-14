# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Decides whether a scheduled evaluation would repeat one already made this month.

Created: 2026-11-09
Last updated: 2026-11-13

This file contains ``redundant_by``, which returns the run whose
``live -> live`` stage already measured an engine inside the window, or
``None``; ``fetch``, which
reads the engine's evaluation runs and their jobs from GitHub; and ``main``,
the command line a scheduled caller's ``decide`` job runs, which writes
``evaluate=true`` or ``evaluate=false`` and a ``reason`` to ``--output``, and
the same decision as markdown to ``--summary`` when given, and exits 0, or
exits 4 without a decision when the history cannot be read.

**An evaluation is a live stage that finished.** A run counts when a job
named ``live -> live on <engine>``, or ``3 - the model (live, live) on
<engine>`` as a run before 2026-11-13 named it, concluded success or failure,
in either caller that runs it: ``evaluate-<engine>-scheduled.yml``, whether a
schedule, the probe or a person started it, and
``evaluate-<engine>-by-claude-on-dispatch.yml``. A failed stage measured the
model, so it counts. A stage skipped, cancelled or never approved did not, and
the run asking is not counted. A local live run leaves no run here and is not
seen.

**The window is 27 days**, shorter than the shortest month, so the previous
month's scheduled run is outside it and cannot make every later month skip.

**A history that cannot be read refuses.** Running would spend on a guess and
skipping would drop a month on one, so the job fails and the run says why.

Specified by ``docs/design/consumer_ci.md`` section 4.18.3.
"""

import argparse
import json
import logging
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Final, Mapping, Optional

from cmn.project_clock import project_today

logger = logging.getLogger(__name__)

WINDOW_DAYS: Final[int] = 27
CALLERS: Final[tuple[str, ...]] = (
    "evaluate-{engine}-scheduled.yml", "evaluate-{engine}-by-claude-on-dispatch.yml")

_ENCODING: Final[str] = "utf-8"
_COUNTED: Final[tuple[str, ...]] = ("success", "failure")
_TIMEOUT_SECONDS: Final[int] = 60
_EXIT_DECIDED: Final[int] = 0
_EXIT_REFUSED: Final[int] = 4

History = tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]]]


def _live_stage(engine: str) -> tuple[str, ...]:
    """Return the names an evaluation gives the jobs that measure the model.

    Args:
        engine (str): The engine evaluated.

    Returns:
        tuple[str, ...]: The ``live -> live`` stage's job name without its band
        or judge, then the name a run before 2026-11-13 gave the same stage.
    """
    return (f"live -> live on {engine}", f"3 - the model (live, live) on {engine}")


def redundant_by(runs: list[dict[str, Any]], jobs_by_run: Mapping[int, list[dict[str, Any]]],
                 engine: str, since: date, current_run: int) -> Optional[str]:
    """Return the newest run whose live stage measured the engine since a date.

    Args:
        runs (list[dict]): Workflow runs, each with ``id``, ``created_at``,
            ``status``, ``event`` and ``path``.
        jobs_by_run (Mapping[int, list[dict]]): Each run's jobs, each with
            ``name`` and ``conclusion``.
        engine (str): The engine a scheduled run would evaluate.
        since (date): The first day of the window.
        current_run (int): The run asking, which never counts.

    Returns:
        Optional[str]: Why this run is redundant, naming the run, its trigger
        and its live stage's conclusion; ``None`` when nothing measured it.
    """
    stages = _live_stage(engine)
    window = [run for run in runs
              if run.get("id") != current_run and run.get("status") == "completed"
              and date.fromisoformat(str(run.get("created_at", ""))[:10]) >= since]
    for run in sorted(window, key=lambda run: str(run.get("created_at")), reverse=True):
        for job in jobs_by_run.get(int(run["id"]), []):
            name = str(job.get("name", ""))
            if any(stage in name for stage in stages) and job.get("conclusion") in _COUNTED:
                return (f"run {run['id']} of {Path(str(run.get('path', ''))).name} "
                        f"({run.get('event')}, {run.get('created_at')}) evaluated {engine} "
                        f"live since {since.isoformat()}, concluding {job.get('conclusion')}")
    return None


def _gh_api(path: str) -> dict[str, Any]:
    """Return one GitHub API response, read through the ``gh`` client.

    Args:
        path (str): The API path.

    Returns:
        dict: The parsed response.

    Raises:
        ValueError: With ``QC_HARNESS_DEPENDENCY_UNMET`` when the call fails
            or returns something that is not JSON.
    """
    done = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                          encoding=_ENCODING, timeout=_TIMEOUT_SECONDS, check=False)
    if done.returncode != 0:
        raise ValueError(f"QC_HARNESS_DEPENDENCY_UNMET: gh api {path} exited "
                         f"{done.returncode}: {done.stderr.strip()[:200]}")
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"QC_HARNESS_DEPENDENCY_UNMET: gh api {path} returned no JSON") \
            from error


def fetch(repository: str, engine: str, since: date) -> History:
    """Read the engine's evaluation runs created since a date, and their jobs.

    Args:
        repository (str): ``owner/name``.
        engine (str): The engine.
        since (date): The first day of the window.

    Returns:
        History: The runs, and each run's jobs by run id.

    Raises:
        ValueError: From the API read.
    """
    runs: list[dict[str, Any]] = []
    for caller in CALLERS:
        listed = _gh_api(f"repos/{repository}/actions/workflows/{caller.format(engine=engine)}"
                         f"/runs?created=>={since.isoformat()}&per_page=100")
        runs.extend(listed.get("workflow_runs") or [])
    jobs_by_run = {int(run["id"]): _gh_api(f"repos/{repository}/actions/runs/{run['id']}"
                                           "/jobs?per_page=100").get("jobs") or []
                   for run in runs if run.get("status") == "completed"}
    return runs, jobs_by_run


def main(argv: Optional[list[str]] = None,
         fetch_history: Callable[[str, str, date], History] = fetch,
         today: Optional[date] = None) -> int:
    """Decide whether this scheduled evaluation should spend.

    Args:
        argv (Optional[list]): Arguments, for calling in-process from a case.
        fetch_history (Callable): Reads the history, replaced in a case.
        today (Optional[date]): The project date, replaced in a case.

    Returns:
        int: ``0`` decided, ``4`` refused with no decision written.
    """
    parser = argparse.ArgumentParser(
        prog="recent-evaluation",
        description="Skip a scheduled evaluation when the engine was evaluated this month")
    parser.add_argument("--engine", required=True)
    parser.add_argument("--repository", required=True, help="owner/name")
    parser.add_argument("--current-run", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="Where to append evaluate= and reason=, the step's output file")
    parser.add_argument("--summary", type=Path, default=None,
                        help="Where to append the decision as markdown, the step summary")
    parsed = parser.parse_args(argv)

    since = (today or project_today()) - timedelta(days=WINDOW_DAYS)
    try:
        runs, jobs_by_run = fetch_history(parsed.repository, parsed.engine, since)
    except ValueError as error:
        logger.error("%s; no decision was made, so nothing is evaluated", error)
        return _EXIT_REFUSED

    reason = redundant_by(runs, jobs_by_run, parsed.engine, since, parsed.current_run)
    decision = "false" if reason else "true"
    reason = reason or (f"no live evaluation of {parsed.engine} since {since.isoformat()}")
    with parsed.output.open("a", encoding=_ENCODING) as output:
        output.write(f"evaluate={decision}\nreason={reason}\n")
    if parsed.summary is not None:
        verdict = "evaluated" if decision == "true" else "skipped"
        with parsed.summary.open("a", encoding=_ENCODING) as summary:
            summary.write(f"## Scheduled evaluation of {parsed.engine}: {verdict}\n\n"
                          f"{reason}\n")
    logger.info("evaluate=%s: %s", decision, reason)
    return _EXIT_DECIDED


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
