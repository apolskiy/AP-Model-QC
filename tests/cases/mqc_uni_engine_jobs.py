# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether each engine is evaluated, named and reported on its own.

Covers ``MQC_CAS_UNI_115709``, inventoried in ``docs/design/consumer_ci.md``
section 4 and designed in sections 4.17 and 4.18.

**Extracted 2026-10-03**, when this subject took ``mqc_uni_workflows.py`` past
the thousand-line ceiling. The subject is one thing: these are the products of
different companies, so an aggregate over them answers no question anybody
asks, and the checks here are what keep the separation from quietly collapsing
back into one job.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

from typing import Any

import allure
import pytest

from tests.cases.workflow_support import (
    WORKFLOWS,
    graded_invocations,
    jobs,
    load,
)

pytestmark = pytest.mark.unit

# THE GATE FOR ONE TARGET, and the caller each target carries.
_GATE = "gate-target.yml"
_GATE_CALLER = "gate-{engine}.yml"
_LIVE = "evaluate-engine.yml"
_WEEKLY_CALLER = "evaluate-{engine}-weekly.yml"

# The engines the roster carries, in the order the gate's calls chain. A
# sequence rather than a set, because the chain is what orders them.
_ROSTERED_ENGINES = ("gemini", "openai", "claude")

def _target_problems(kind: str, pattern: str, called: str) -> list[str]:
    """Report a target that is not a workflow of its own.

    Args:
        kind (str): ``gate`` or ``weekly``, for the message.
        pattern (str): The caller filename, with an ``{engine}`` placeholder.
        called (str): The workflow a caller is expected to invoke.

    Returns:
        list[str]: One entry per problem.
    """
    problems: list[str] = []
    for engine in _ROSTERED_ENGINES:
        name = pattern.format(engine=engine)
        if not (WORKFLOWS / name).is_file():
            problems.append(
                f"{name} is absent, so {engine} has no {kind} of its own and "
                f"its conclusion would be another target's too"
            )
            continue
        loaded = load(name)
        calls = [
            job for job in jobs(loaded).values()
            if called in str(job.get("uses") or "")
        ]
        if not calls:
            problems.append(f"{name} does not call {called}")
        for job in calls:
            if str(((job.get("with") or {}).get("engine")) or "") != engine:
                problems.append(f"{name} calls {called} for another target")
        group = str(((loaded.get("concurrency") or {}).get("group")) or "")
        if engine not in group:
            problems.append(
                f"{name} has no concurrency group of its own, so one target's "
                f"run could supersede another's"
            )
    return problems


def _weekly_problems() -> list[str]:
    """Report a weekly caller carrying a schedule the design withholds.

    A live firing spends real money, and `consumer_ci.md` section 4.18.3 names
    what has to exist first: the known findings triaged, and a run that
    declines when this target was already evaluated in the window.

    Returns:
        list[str]: One entry per premature schedule.
    """
    problems: list[str] = []
    for engine in _ROSTERED_ENGINES:
        name = _WEEKLY_CALLER.format(engine=engine)
        if not (WORKFLOWS / name).is_file():
            continue
        triggers = load(name).get("on") or load(name).get(True) or {}
        if isinstance(triggers, dict) and "schedule" in triggers:
            problems.append(
                f"{name} carries a schedule, and section 4.18.3 withholds one "
                f"until the known findings are triaged and a run declines when "
                f"this target was already evaluated in the window"
            )
    return problems


def _band_problems(graded: dict[str, Any]) -> list[str]:
    """Report bands naming their engine literally or sharing an artifact name.

    Args:
        graded (dict): The loaded per-target gate.

    Returns:
        list[str]: One entry per problem.
    """
    problems: list[str] = []
    for job_name, job in jobs(graded).items():
        for body in graded_invocations(job):
            if "inputs.engine" not in body:
                problems.append(
                    f"{_GATE}:{job_name} names its engine literally rather "
                    f"than taking it from the call"
                )
        for step in job.get("steps") or []:
            if "upload-artifact" not in str(step.get("uses") or ""):
                continue
            name = str(((step.get("with") or {}).get("name")) or "")
            if name and "inputs.engine" not in name and graded_invocations(job):
                problems.append(
                    f"{_GATE}:{job_name} uploads {name!r}, which is not keyed "
                    f"by the engine, so two targets share a name"
                )
    return problems


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCEngineAttribution:
    """A target's result is its own, down to the workflow that produced it."""

    @allure.story("Every target is its own workflow")
    def MQC_CAS_UNI_115709_a_graded_job_not_naming_its_engine_is_reported(
        self,
    ) -> None:
        """Each target is its own workflow, named, and nothing aggregates.

        A target is an engine at a model version, and a graded failure is a
        finding about one of them. **A workflow run has a conclusion**, so
        three targets inside one gate produced a red run when two passed; the
        separation has to be at the workflow level, not the job level.

        Four properties:

        * the per-target gate takes its engine from an input, never a literal,
        * every rostered target has a gate caller **and** a weekly caller,
        * each caller names its target and keys its own concurrency group,
        * the artifacts a graded job uploads are keyed by the engine, because
          two targets sharing an artifact name is one name and the later
          upload wins.

        Design: ``consumer_ci.md`` sections 4.18 and 4.19.

        Returns:
            None
        """
        gate = load(_GATE)

        declared = (
            ((gate.get("on") or gate.get(True) or {}).get("workflow_call") or {})
            .get("inputs") or {}
        )
        assert "engine" in declared, (
            f"{_GATE} declares no engine input, so it cannot be per target"
        )
        assert jobs(gate), f"{_GATE} declares no jobs"

        problems = _band_problems(gate)
        problems.extend(_target_problems("gate", _GATE_CALLER, _GATE))
        problems.extend(_target_problems("weekly", _WEEKLY_CALLER, _LIVE))
        problems.extend(_weekly_problems())

        assert not problems, (
            "targets do not each have a workflow of their own: "
            + "; ".join(problems)
        )
