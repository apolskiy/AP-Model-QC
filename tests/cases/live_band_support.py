# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading the banded regression run, for the cases that check it.

Created: 2026-11-12
Last updated: 2026-11-15

This file contains the pair names, candidate mode then judge mode;
``STAGES``, ``BANDS`` and ``BAND_SUFFIXES``, the regression run's three
``live -> live`` band jobs as ``consumer_ci.md`` sections 7.8.1 and 7.9.2 lay
them out; ``RETIRED_JOB_PREFIXES``, the replay stages' job names, which no
regression run job may carry; ``REGRESSION_JOBS``, every job a regression run
holds, in order; ``LIVE_BANDS``, the three that spend, in the order they run;
``band_step``, which returns the step calling the
shared band definition; ``band_invocation``, the band's pytest invocation with
the step's inputs resolved; ``flag_value``, the value an invocation passes a
flag; ``steps_running``, the steps whose run body names a text;
``regression_callers``, every workflow calling the regression run;
``replaying_invocations``, every regression run invocation naming replay;
``live_jobs_off_their_environment``, every job running a case live outside
the environment its workflow requires; ``claude_judged_callers``, the judge
each counted claude-judged caller passes; ``write_band_report``, a band
report carrying a published spend; and ``write_floor_report``, a P2-P4 band report the floor reads.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.
"""

import re
from pathlib import Path
from typing import Any, Final, Optional

from tests.cases.debug_support import environment_of, expected_environment
from tests.cases.workflow_support import (
    BAND_ACTION,
    WORKFLOWS,
    graded_invocations,
    jobs,
    load,
    run_lines,
)

# THE REGRESSION RUN EVERY ENGINE'S CALLERS INVOKE.
REGRESSION_RUN: Final[str] = "evaluate-engine.yml"

# THE STAGE NAMES, candidate mode then judge mode. Section 7.0.
REPLAY_REPLAY: Final[str] = "replay -> replay"
REPLAY_LIVE: Final[str] = "replay -> live"
LIVE_LIVE: Final[str] = "live -> live"

# THE ONE STAGE A REGRESSION RUN HOLDS, by its pair: its jobs in band order,
# the report stem and carried-outcomes prefix each band job uses, the name each
# job's display name leads with, and the candidate and judge modes its band
# invocation passes. `replay -> replay` and `replay -> live` left the
# regression run on 2026-11-14. Sections 7.8.1 and 7.9.2.
STAGES: Final[dict[str, dict[str, Any]]] = {
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
LIVE_BANDS: Final[tuple[str, ...]] = STAGES[LIVE_LIVE]["jobs"]

# THE JOB NAMES OF THE RETIRED REPLAY STAGES, which no regression run job may
# carry. Section 7.9.
RETIRED_JOB_PREFIXES: Final[tuple[str, ...]] = ("replay-replay-", "replay-live-")

# THE JOBS AHEAD OF THE BANDS, in order, and then every job a regression run
# holds besides its report. Section 7.9.2.
PRECONDITIONS_JOB: Final[str] = "preconditions"
CALIBRATION_JOB: Final[str] = "calibration"
REGRESSION_JOBS: Final[tuple[str, ...]] = (
    "resolve", PRECONDITIONS_JOB, CALIBRATION_JOB, *LIVE_BANDS,
)

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


def replaying_invocations(regression: dict[str, Any], root: Path) -> list[str]:
    """Return every regression run invocation naming replay as a candidate or judge mode.

    Args:
        regression (dict): The regression run's jobs, by name.
        root (Path): The repository root.

    Returns:
        list[str]: Each job name and invocation, empty where nothing replays.
    """
    return [
        f"{name}: {line.strip()}"
        for name, job in regression.items()
        for line in run_lines(job, root)
        if "replay" in (flag_value(line, "--mode"), flag_value(line, "--judge-mode"))
    ]


def live_jobs_off_their_environment(root: Path) -> list[str]:
    """Return every job running a case live without the environment its workflow requires.

    Args:
        root (Path): The repository root.

    Returns:
        list[str]: Each workflow and job, empty where every live job names its environment.
    """
    return [
        f"{workflow.name}:{name}"
        for workflow in sorted(WORKFLOWS.glob("*.yml"))
        for name, job in jobs(load(workflow.name)).items()
        if any(flag_value(line, "--mode") == "live"
               or flag_value(line, "--judge-mode") == "live"
               for line in run_lines(job, root))
        and environment_of(job) != expected_environment(workflow.name, name)
    ]


def claude_judged_callers(engines: tuple[str, ...], uncounted: str) -> dict[str, list[str]]:
    """Return the judge each counted claude-judged caller of each engine passes.

    Args:
        engines (tuple[str, ...]): The engines to read callers for.
        uncounted (str): The filename suffix of a cadence that is not counted.

    Returns:
        dict[str, list[str]]: Engine to the judge each of its callers' jobs passes.
    """
    return {
        engine: [
            str((job.get("with") or {}).get("judge"))
            for found in sorted(WORKFLOWS.glob(f"evaluate-{engine}-by-claude-*.yml"))
            if not found.stem.endswith(uncounted)
            for job in jobs(load(found.name)).values()
        ]
        for engine in engines
    }


def write_band_report(directory: Path, stem: str, total: Optional[str]) -> Path:
    """Write a band's JUnit report carrying a published spend, as a live band leaves one.

    Args:
        directory (Path): Where the report goes, created where absent.
        stem (str): The report's stem, such as ``live_live_p0``.
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


def write_floor_report(directory: Path, passed: int, skipped: int) -> Path:
    """Write a P2-P4 band's JUnit report with no failure, as the floor reads one.

    Args:
        directory (Path): Where the report goes, created where absent.
        passed (int): How many cases passed.
        skipped (int): How many skipped.

    Returns:
        Path: The report written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    cases = "".join(f'<testcase name="MQC_CAS_EVAL_13400{index}_passes"/>'
                    for index in range(passed))
    cases += "".join(f'<testcase name="MQC_CAS_EVAL_13410{index}_skips"><skipped/></testcase>'
                     for index in range(skipped))
    report = directory / "junit_mqc_live_live_p2_p4.xml"
    report.write_text(
        '<?xml version="1.0"?><testsuites><testsuite '
        f'tests="{passed + skipped}" failures="0" errors="0" skipped="{skipped}">'
        f"{cases}</testsuite></testsuites>",
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
