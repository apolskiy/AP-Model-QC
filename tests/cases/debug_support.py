# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading the debug workflow, for the cases that check what it may spend.

Created: 2026-11-14
Last updated: 2026-11-14

This file contains the debug workflow's file name, its two job names, the
environment its live job names and the limit on a live selection;
``debug_jobs``, the workflow's jobs; ``provider_secrets``, the provider keys a
job references; ``environment_of``, the environment a job names;
``expected_environment``, the environment a job running a case live must name;
and ``jobs_naming``, every job in every workflow naming a given environment.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by ``docs/design/consumer_ci.md`` section 6.5.
"""

import re
from typing import Any, Final

import yaml

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
