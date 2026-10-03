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
    needs,
)

pytestmark = pytest.mark.unit

_GATE = "gate-on-change.yml"
_GRADED_ENGINE = "graded-engine.yml"
_LIVE = "evaluate-engine.yml"
_WEEKLY_CALLER = "evaluate-{engine}-weekly.yml"

# The engines the roster carries, in the order the gate's calls chain. A
# sequence rather than a set, because the chain is what orders them.
_ROSTERED_ENGINES = ("gemini", "openai", "claude")

def _weekly_problems() -> list[str]:
    """Report a weekly ladder that is not one workflow per engine.

    Each engine has its own caller, so it has its own status, its own run
    history and its own artifacts: a combined weekly result would average over
    three vendors' products. Each caller also guards against overlapping
    **itself**, which is the use `testing-standards.md` section 2 endorses
    concurrency for.

    **No cron yet, deliberately.** A live firing spends real money and section
    4.18.3 names what has to exist first, so a schedule appearing here before
    then is reported rather than welcomed.

    Design: ``consumer_ci.md`` section 4.18.

    Returns:
        list[str]: One entry per problem.
    """
    problems: list[str] = []
    for engine in _ROSTERED_ENGINES:
        name = _WEEKLY_CALLER.format(engine=engine)
        path = WORKFLOWS / name
        if not path.is_file():
            problems.append(
                f"{name} is absent, so {engine} has no weekly evaluation of "
                f"its own and its result would be aggregated with another's"
            )
            continue
        loaded = load(name)
        calls = [
            job for job in jobs(loaded).values()
            if _LIVE in str(job.get("uses") or "")
        ]
        if not calls:
            problems.append(f"{name} does not call {_LIVE}")
        for job in calls:
            if str(((job.get("with") or {}).get("engine")) or "") != engine:
                problems.append(f"{name} calls the ladder for another engine")
        group = str(((loaded.get("concurrency") or {}).get("group")) or "")
        if engine not in group:
            problems.append(
                f"{name} has no concurrency group of its own, so two runs of "
                f"{engine} could overlap, or three engines could contend"
            )
        triggers = loaded.get("on") or loaded.get(True) or {}
        if isinstance(triggers, dict) and "schedule" in triggers:
            problems.append(
                f"{name} carries a schedule, and section 4.18.3 withholds one "
                f"until the known findings are triaged and a run declines when "
                f"this engine was already evaluated in the window"
            )
    return problems

def _band_problems(graded: dict[str, Any]) -> list[str]:
    """Report bands naming their engine literally or sharing an artifact name.

    Args:
        graded (dict): The loaded graded-engine workflow.

    Returns:
        list[str]: One entry per problem.
    """
    problems: list[str] = []
    for job_name, job in jobs(graded).items():
        for body in graded_invocations(job):
            if "inputs.engine" not in body:
                problems.append(
                    f"{_GRADED_ENGINE}:{job_name} names its engine literally "
                    f"rather than taking it from the call"
                )
        for step in job.get("steps") or []:
            if "upload-artifact" not in str(step.get("uses") or ""):
                continue
            name = str(((step.get("with") or {}).get("name")) or "")
            if name and "inputs.engine" not in name:
                problems.append(
                    f"{_GRADED_ENGINE}:{job_name} uploads {name!r}, which is "
                    f"not keyed by the engine, so two engines share a name"
                )
    return problems

def _engine_callers(gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the gate jobs that call the graded workflow, keyed by engine.

    Args:
        gate (dict): The loaded gate workflow.

    Returns:
        dict: Engine name to the job that measures it.
    """
    callers: dict[str, dict[str, Any]] = {}
    for name, job in jobs(gate).items():
        if _GRADED_ENGINE not in str(job.get("uses") or ""):
            continue
        engine = str(((job.get("with") or {}).get("engine")) or "")
        callers[engine] = {**job, "job_name": name}
    return callers

@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCEngineAttribution:
    """A graded red has to say which model it is about."""

    @allure.story("Every graded job names its engine")
    def MQC_CAS_UNI_115709_a_graded_job_not_naming_its_engine_is_reported(
        self,
    ) -> None:
        """Each engine is a separate job, named, chained and independently red.

        A graded failure is a finding about one model. A matrix would make the
        engines legs of one job whose status aggregates, so one engine's
        finding would redden a check covering three; separate calls give each
        its own status, its own re-run and its own diagnosis.

        Four properties, each of which has already gone wrong somewhere:

        * the graded bands take their engine from an input, never a literal,
        * every rostered engine has a call, so none is measured by nothing,
        * each caller's job name carries its engine, so a red is attributable
          in a listing,
        * the calls are chained **and** each carries a status function, because
          `needs:` alone would skip the next engine when one goes red, which is
          the coupling the separation removes.

        **The artifacts are keyed by the engine too.** Two engines sharing an
        artifact name is one name, and the later upload wins: the defect
        ``JudgementKey`` had before it carried the candidate engine.

        Design: ``consumer_ci.md`` sections 4.17 and 4.17.3.

        Returns:
            None
        """
        problems: list[str] = []
        gate = load(_GATE)
        graded = load(_GRADED_ENGINE)

        # THE BANDS TAKE THEIR ENGINE FROM AN INPUT.
        assert "engine" in (
            ((graded.get("on") or graded.get(True) or {}).get("workflow_call") or {})
            .get("inputs") or {}
        ), f"{_GRADED_ENGINE} declares no engine input, so it cannot be per engine"

        assert jobs(graded), f"{_GRADED_ENGINE} declares no jobs"
        problems.extend(_band_problems(graded))

        # EVERY ROSTERED ENGINE HAS A CALL, AND THE CALLS ARE CHAINED.
        callers = _engine_callers(gate)
        missing = sorted(set(_ROSTERED_ENGINES) - set(callers))
        assert not missing, (
            f"{_GATE} calls {_GRADED_ENGINE} for {sorted(callers)} and not for "
            f"{missing}, so those engines are measured by nothing"
        )

        for position, engine in enumerate(_ROSTERED_ENGINES):
            job = callers[engine]
            name = job["job_name"]
            if engine not in str(job.get("name") or ""):
                problems.append(
                    f"{_GATE}:{name} does not name its engine, so a red names "
                    f"no model"
                )
            condition = str(job.get("if") or "")
            if "cancelled()" not in condition and "always()" not in condition:
                problems.append(
                    f"{_GATE}:{name} carries no status function, so an engine "
                    f"before it going red would skip it entirely"
                )
            if position:
                previous = callers[_ROSTERED_ENGINES[position - 1]]["job_name"]
                if previous not in needs(job):
                    problems.append(
                        f"{_GATE}:{name} does not need {previous}, so the "
                        f"engines are not sequenced"
                    )

        problems.extend(_weekly_problems())

        assert not problems, (
            "graded jobs do not attribute their results to one engine: "
            + "; ".join(problems)
        )
