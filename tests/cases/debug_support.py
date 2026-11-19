# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading the debug workflow, for the cases that check what it may spend.

Created: 2026-11-14
Last updated: 2026-11-19

This file contains the debug workflow's file name, its two job names, the
environment its live job names and the limit on a live selection;
``debug_jobs``, the workflow's jobs; ``provider_secrets``, the provider keys a
job references; ``environment_of``, the environment a job names;
``expected_environment``, the environment a job running a case live must name;
``jobs_naming``, every job in every workflow naming a given environment; and
``pytest_steps``, ``passes_input``, ``passes_observations`` and
``passes_escalation_target``, which read whether a job passes the dispatch
form's observation count and escalation target to pytest; ``states_outcome``,
which reads whether a job ends by stating what pytest did; and
``write_junit``, which writes a JUnit report for the tool that states it; and
``outcome_headline``, which runs that tool on such a report.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by ``docs/design/consumer_ci.md`` sections 6.5, 6.5.1, 6.5.2 and 6.5.3.
"""

import re
from pathlib import Path
from typing import Any, Final

import yaml

from tools.debug_outcome import main as debug_outcome

from tests.cases.workflow_support import WORKFLOWS, jobs, load

DEBUG_WORKFLOW: Final[str] = "debug-cases-on-demand.yml"
DEBUG_REPLAY: Final[str] = "debug_replay"
DEBUG_LIVE: Final[str] = "debug_live"
# The environment debug_live names. It carries the owner as required reviewer,
# which is what makes a live debug run wait for approval.
DEBUG_ENVIRONMENT: Final[str] = "debug_live"
# The environment the regression run and judge calibration name, main only.
LIVE_ENVIRONMENT: Final[str] = "live"
MAX_LIVE_TESTS: Final[int] = 20
DEFAULT_LIVE_CEILING: Final[str] = "0.50"
# Where a live run writes recordings and judgements, and where the live job
# copies them inside its artifact.
RECORDINGS: Final[str] = "tests/fixtures/replay"
ARTIFACT_RECORDINGS: Final[str] = "debug-artifacts/recordings"
# The dispatch input setting the observation count, the environment variable
# carrying it into a run step, and the argument that step expands, which adds
# nothing when the input is empty.
OBSERVATIONS_INPUT: Final[str] = "observations"
OBSERVATIONS_VARIABLE: Final[str] = "OBSERVATIONS"
OBSERVATIONS_ARGUMENT: Final[str] = '${OBSERVATIONS:+--observations "${OBSERVATIONS}"}'
# The same three for the total a failing case escalates to (section 6.5.2).
ESCALATE_TO_INPUT: Final[str] = "escalate_to"
ESCALATE_TO_VARIABLE: Final[str] = "ESCALATE_TO"
ESCALATE_TO_ARGUMENT: Final[str] = '${ESCALATE_TO:+--escalate-to "${ESCALATE_TO}"}'
# The boolean input adding the foundations a named case rests on, and the
# expression adding the flag only when it is on (section 6.5.4).
WITH_PREREQUISITES_INPUT: Final[str] = "with_prerequisites"
WITH_PREREQUISITES_ARGUMENT: Final[str] = (
    "${{ inputs.with_prerequisites && '--with-prerequisites' || '' }}"
)
# The tool each debug job ends with, stating what pytest did (section 6.5.3),
# and the option naming the JUnit report a pytest step writes.
OUTCOME_TOOL: Final[str] = "tools/debug_outcome.py"
JUNIT_OPTION: Final[re.Pattern[str]] = re.compile(r"--junitxml[= ](\S+)")


def debug_workflow() -> dict[str, Any]:
    """Return the debug workflow, parsed.

    Returns:
        dict: The parsed document.
    """
    return load(DEBUG_WORKFLOW)


def debug_jobs() -> dict[str, dict[str, Any]]:
    """Return the debug workflow's jobs.

    Returns:
        dict: Job name to its definition.
    """
    return jobs(debug_workflow())


def dispatch_inputs() -> dict[str, Any]:
    """Return the debug workflow's dispatch inputs.

    Returns:
        dict: Input name to its declaration. YAML reads the ``on`` key as True.
    """
    workflow = debug_workflow()
    triggers = workflow.get(True) or workflow.get("on") or {}
    return dict((triggers.get("workflow_dispatch") or {}).get("inputs") or {})


def provider_secrets(job: dict[str, Any]) -> set[str]:
    """Return the provider keys a job references.

    Args:
        job (dict): A parsed job.

    Returns:
        set: Secret names other than the automatic token, which buys no quota.
    """
    text = yaml.safe_dump(job, sort_keys=False)
    return set(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text)) - {"GITHUB_TOKEN"}


def environment_of(job: dict[str, Any]) -> str:
    """Return the environment a job names, however it spells it.

    Args:
        job (dict): A parsed job.

    Returns:
        str: The environment's name, or empty where the job names none.
    """
    declared = job.get("environment") or ""
    if isinstance(declared, dict):
        return str(declared.get("name") or "")
    return str(declared)


def expected_environment(workflow: str, job: str) -> str:
    """Return the environment a job running a case live must name.

    Args:
        workflow (str): The workflow's file name.
        job (str): The job's name.

    Returns:
        str: ``debug_live`` for the debug workflow's live job, ``live`` for any other.
    """
    if (workflow, job) == (DEBUG_WORKFLOW, DEBUG_LIVE):
        return DEBUG_ENVIRONMENT
    return LIVE_ENVIRONMENT


def jobs_naming(environment: str) -> list[str]:
    """Return every job in every workflow naming an environment.

    Args:
        environment (str): The environment's name.

    Returns:
        list: ``<workflow>:<job>`` per job naming it, in file order.
    """
    return [
        f"{path.name}:{name}"
        for path in sorted(WORKFLOWS.glob("*.yml"))
        for name, job in jobs(load(path.name)).items()
        if environment_of(job) == environment
    ]


def step_bodies(job: dict[str, Any]) -> list[tuple[str, str]]:
    """Return each step's condition and run body.

    Args:
        job (dict): A parsed job.

    Returns:
        list: Pairs of the step's ``if`` and its ``run``, empty where absent.
    """
    return [
        (str((step or {}).get("if") or ""), str((step or {}).get("run") or ""))
        for step in job.get("steps") or []
    ]


def pytest_steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the steps of a job whose run body invokes pytest.

    Args:
        job (dict): A parsed job.

    Returns:
        list: Each such step, in job order.
    """
    return [
        step for step in job.get("steps") or []
        if str((step or {}).get("run") or "").lstrip().startswith("pytest ")
    ]


def passes_input(job: dict[str, Any], name: str, variable: str, argument: str) -> bool:
    """Return whether every pytest step of a job passes a dispatch input when set.

    Args:
        job (dict): A parsed job.
        name (str): The dispatch input.
        variable (str): The environment variable carrying it into the step.
        argument (str): The expansion adding the flag only when it is set.

    Returns:
        bool: True when the job has a pytest step and each maps the input into
        its environment and expands the argument in its body.
    """
    found = pytest_steps(job)
    return bool(found) and all(
        str((step.get("env") or {}).get(variable) or "") == f"${{{{ inputs.{name} }}}}"
        and argument in str(step.get("run") or "")
        for step in found
    )


def passes_observations(job: dict[str, Any]) -> bool:
    """Return whether every pytest step of a job passes the observation count when set.

    Args:
        job (dict): A parsed job.

    Returns:
        bool: As :func:`passes_input` for ``observations``.
    """
    return passes_input(job, OBSERVATIONS_INPUT, OBSERVATIONS_VARIABLE, OBSERVATIONS_ARGUMENT)


def passes_escalation_target(job: dict[str, Any]) -> bool:
    """Return whether every pytest step of a job passes the escalation target when set.

    Args:
        job (dict): A parsed job.

    Returns:
        bool: As :func:`passes_input` for ``escalate_to``.
    """
    return passes_input(job, ESCALATE_TO_INPUT, ESCALATE_TO_VARIABLE, ESCALATE_TO_ARGUMENT)


def passes_prerequisites_choice(job: dict[str, Any]) -> bool:
    """Return whether every pytest step of a job adds ``--with-prerequisites`` only when asked.

    Args:
        job (dict): A parsed job.

    Returns:
        bool: True when the job has a pytest step, each expands the input's
        expression, and none passes the flag unconditionally.
    """
    found = pytest_steps(job)
    return bool(found) and all(
        WITH_PREREQUISITES_ARGUMENT in str(step.get("run") or "")
        and str(step.get("run") or "").replace(WITH_PREREQUISITES_ARGUMENT, "").count(
            "--with-prerequisites") == 0
        for step in found
    )


def states_outcome(job: dict[str, Any]) -> str:
    """Return why a job does not state its pytest outcome first, or empty when it does.

    Args:
        job (dict): A parsed job.

    Returns:
        str: Empty when the step straight after the job's pytest step runs
        always and passes :data:`OUTCOME_TOOL` the JUnit path that step
        writes; otherwise what is missing.
    """
    found = pytest_steps(job)
    written = JUNIT_OPTION.search(str((found[0] if found else {}).get("run") or ""))
    if written is None:
        return "no pytest step writing a JUnit report"
    entries = list(job.get("steps") or [])
    position = next(index for index, entry in enumerate(entries) if entry is found[0])
    following = entries[position + 1] if position + 1 < len(entries) else {}
    condition, body = str(following.get("if") or ""), str(following.get("run") or "")
    if OUTCOME_TOOL not in body:
        return f"the step after pytest does not run {OUTCOME_TOOL}"
    if "always()" not in condition:
        return f"the step after pytest runs when {condition!r}, not always"
    if written.group(1) not in body:
        return f"the step after pytest does not read {written.group(1)}"
    return ""


def write_junit(path: Path, testcases: list[str]) -> Path:
    """Write a JUnit report holding the given testcase elements.

    Args:
        path (Path): Where to write it.
        testcases (list[str]): Each a ``testcase`` element, as XML text.

    Returns:
        Path: The path written.
    """
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">'
        + "".join(testcases) + "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def outcome_headline(folder: Path, cases: list[str]) -> tuple[int, str]:
    """Return the outcome tool's exit code and summary headline for a report of these cases.

    Args:
        folder (Path): A directory to create for the report and the summary.
        cases (list[str]): The report's testcase elements, as XML text.

    Returns:
        tuple: The exit code and the summary's first line.
    """
    folder.mkdir()
    report = write_junit(folder / "junit.xml", cases)
    summary = folder / "summary.md"
    exit_code = debug_outcome([str(report), "--summary", str(summary)])
    return exit_code, summary.read_text(encoding="utf-8").splitlines()[0]
