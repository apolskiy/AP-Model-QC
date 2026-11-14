# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading the banded regression run, for the cases that check it.

Created: 2026-11-12
Last updated: 2026-11-13

This file contains the three stage names, candidate mode then judge mode;
``STAGES``, ``BANDS`` and ``BAND_SUFFIXES``, the regression run's nine band
jobs as ``consumer_ci.md`` section 7.8.1 lays them out; ``LIVE_BANDS``, the six that
spend, in the order they run; ``band_step``, which returns the step calling the
shared band definition; ``band_invocation``, the band's pytest invocation with
the step's inputs resolved; ``flag_value``, the value an invocation passes a
flag; ``steps_running``, the steps whose run body names a text; and
``regression_callers``, every workflow calling the regression run.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.
"""

import re
from pathlib import Path
from typing import Any, Final, Optional

from tests.cases.workflow_support import (
    BAND_ACTION,
    WORKFLOWS,
    graded_invocations,
    jobs,
    load,
)

# THE REGRESSION RUN EVERY ENGINE'S CALLERS INVOKE.
REGRESSION_RUN: Final[str] = "evaluate-engine.yml"

# THE STAGE NAMES, candidate mode then judge mode. Section 7.0.
REPLAY_REPLAY: Final[str] = "replay -> replay"
REPLAY_LIVE: Final[str] = "replay -> live"
LIVE_LIVE: Final[str] = "live -> live"

# EACH STAGE BY ITS PAIR, in the order the stages run: its jobs in band order,
# the report stem and carried-outcomes prefix each band job uses, the name each
# job's display name leads with, and the candidate and judge modes its band
# invocation passes. `replay -> replay` passes no judge mode, so the judge
# follows the replayed candidate. Section 7.8.1.
STAGES: Final[dict[str, dict[str, Any]]] = {
    REPLAY_REPLAY: {
        "jobs": ("replay-replay-p0", "replay-replay-p1", "replay-replay-lower"),
        "report": "replay_replay",
        "carry": "carry-replay-replay-after-",
        "name": "replay -> replay on ${{ inputs.engine }}",
        "mode": "replay",
        "judge_mode": "",
    },
    REPLAY_LIVE: {
        "jobs": ("replay-live-p0", "replay-live-p1", "replay-live-lower"),
        "report": "replay_live",
        "carry": "carry-replay-live-after-",
        "name": "replay -> live on ${{ inputs.engine }}",
        "mode": "replay",
        "judge_mode": "live",
    },
    LIVE_LIVE: {
        "jobs": ("live-live-p0", "live-live-p1", "live-live-lower"),
        "report": "live_live",
        "carry": "carry-live-live-after-",
        "name": "live -> live on ${{ inputs.engine }}",
        "mode": "live",
        "judge_mode": "live",
    },
}

# THE GATE'S THREE BANDS, as each band job passes them: the band's name, its
# priority expression and whether it blocks a release. Section 3.12.
BANDS: Final[tuple[tuple[str, str, str], ...]] = (
    ("P0", "0", "true"),
    ("P1", "1", "true"),
    ("P2-P4", "2,3,4", "false"),
)

# EACH BAND'S REPORT STEM SUFFIX, in the order of ``BANDS``. Section 7.8.1.
BAND_SUFFIXES: Final[tuple[str, ...]] = ("p0", "p1", "p2_p4")

# THE BANDS THAT SPEND, in the order they run, so a band's position is how
# many live bands ran before it. Section 7.8.4.
LIVE_BANDS: Final[tuple[str, ...]] = STAGES[REPLAY_LIVE]["jobs"] + STAGES[LIVE_LIVE]["jobs"]

# THE PLATFORM A LIVE RUN TAKES WHEN NOBODY CHOOSES, and the two a dispatch
# offers. Section 7.8.3.
DEFAULT_OS: Final[str] = "ubuntu-26.04"
OFFERED_OS: Final[tuple[str, ...]] = ("ubuntu-26.04", "windows-latest")

# WHERE A JUDGE'S CALIBRATION RECORD IS COMMITTED. Section 7.4.5.
RECORD_PATH: Final[str] = "records/calibration/${{ inputs.judge }}.json"


def band_step(job: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Return the step calling the shared band definition, or None.

    Args:
        job (dict): The job definition.

    Returns:
        Optional[dict]: The step, None where the job calls no band.
    """
    for step in job.get("steps") or []:
        if str((step or {}).get("uses") or "") == BAND_ACTION:
            return step
    return None


def band_inputs(job: dict[str, Any]) -> dict[str, str]:
    """Return what a job passes the band definition, each value as text.

    Args:
        job (dict): The job definition.

    Returns:
        dict[str, str]: Input name to value, empty where the job calls no band.
    """
    step = band_step(job) or {}
    return {name: str(value) for name, value in (step.get("with") or {}).items()}


def band_invocation(job: dict[str, Any], root: Path) -> str:
    """Return a band job's graded invocation, the step's inputs resolved.

    Args:
        job (dict): The job definition.
        root (Path): The repository root.

    Returns:
        str: The one graded invocation, empty where the job makes none or more
        than one, which a caller reports.
    """
    found = graded_invocations(job, root)
    return found[0] if len(found) == 1 else ""


def pair_mismatch(job: dict[str, Any], stage: dict[str, Any], position: int) -> Optional[str]:
    """Return how a band job's report stem or carried outcomes miss its stage's pair, or None.

    Args:
        job (dict): The band job definition.
        stage (dict): The stage's entry in ``STAGES``.
        position (int): The band's position in ``BANDS``.

    Returns:
        Optional[str]: The stem and the carried artifacts, None where both
        carry the pair.
    """
    report = band_inputs(job).get("report")
    carried = [
        str((entry.get("with") or {}).get("name", ""))
        for entry in job.get("steps") or []
        if "upload-artifact" in str(entry.get("uses", ""))
        and str((entry.get("with") or {}).get("name", "")).startswith("carry-")
    ]
    if report == f"{stage['report']}_{BAND_SUFFIXES[position]}" and all(
            artifact.startswith(stage["carry"]) for artifact in carried):
        return None
    return f"report {report!r}, carries {carried}"


def flag_value(line: str, flag: str) -> Optional[str]:
    """Return the value an invocation passes a flag, quotes removed.

    Args:
        line (str): A folded run body.
        flag (str): The flag, such as ``--mode``.

    Returns:
        Optional[str]: The value, None where the flag is absent.
    """
    found = re.search(rf'{re.escape(flag)}(?:\s+|=)(?:"([^"]*)"|(\S+))', line)
    if found is None:
        return None
    return found.group(1) if found.group(1) is not None else found.group(2)


def steps_running(job: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """Return the steps whose run body names a text.

    Args:
        job (dict): The job definition.
        text (str): What the run body must contain.

    Returns:
        list[dict]: The steps, in order.
    """
    return [
        step for step in job.get("steps") or []
        if text in str((step or {}).get("run") or "")
    ]


def regression_callers() -> dict[str, dict[str, Any]]:
    """Return every workflow calling the regression run, by filename.

    Returns:
        dict[str, dict]: Filename to the parsed caller.
    """
    found: dict[str, dict[str, Any]] = {}
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        loaded = load(workflow.name)
        if any(REGRESSION_RUN in str(job.get("uses") or "") for job in jobs(loaded).values()):
            found[workflow.name] = loaded
    return found


def write_band_report(directory: Path, stem: str, total: Optional[str]) -> Path:
    """Write a band's JUnit report carrying a published spend, as a live band leaves one.

    Args:
        directory (Path): Where the report goes, created where absent.
        stem (str): The report's stem, such as ``replay_live_p0``.
        total (Optional[str]): The ``mqc.total_spend_usd`` value, such as
            ``1.2345`` or ``unpriced``; None writes no spend property.

    Returns:
        Path: The report written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    spent = (f'<property name="mqc.total_spend_usd" value="{total}"/>'
             if total is not None else "")
    report = directory / f"junit_mqc_{stem}.xml"
    report.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" '
        f'tests="1"><properties><property name="mqc.engine" value="grok"/>{spent}'
        '</properties><testcase classname="c" name="t"/></testsuite></testsuites>',
        encoding="utf-8",
    )
    return report


def dispatch_inputs(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the inputs a workflow's manual dispatch declares.

    Args:
        workflow (dict): The parsed workflow.

    Returns:
        dict: Input name to its declaration, empty where it declares none.
    """
    triggers = workflow.get("on") or workflow.get(True) or {}
    return dict(((triggers.get("workflow_dispatch") or {}) if isinstance(triggers, dict)
                 else {}).get("inputs") or {})


def call_inputs(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the inputs a called workflow declares.

    Args:
        workflow (dict): The parsed workflow.

    Returns:
        dict: Input name to its declaration, empty where it declares none.
    """
    triggers = workflow.get("on") or workflow.get(True) or {}
    return dict(((triggers.get("workflow_call") or {}) if isinstance(triggers, dict)
                 else {}).get("inputs") or {})
