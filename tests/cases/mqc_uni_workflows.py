# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""What the workflows must and must not do.

Covers ``MQC_CAS_UNI_115700``, ``115701``, ``115702`` and ``115703``, inventoried
in ``docs/testing/model_evaluation_test_plan.md`` section 8.1.

**Workflow files are configuration, not collected code**, so ``pytest.ini``
never sees them and ``.pylintrc`` is not run against them. Their properties are
therefore asserted here, by reading them, which is the same approach the harness
takes to its own.

A failure here is our defect, so the module carries no priority marker.
"""

import re
from pathlib import Path
from typing import Any

import allure
import pytest
import yaml

from cmn.code_standards import artifact_mandate_gaps

pytestmark = pytest.mark.unit

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# The prefix a downstream collector matches. A debug run must not carry it.
_COLLECTOR_PREFIX = "mqc-reports-"

# The workflows the ladder is split across, and the rungs in order.
_GATE = "gate-on-change.yml"
_LIVE = "evaluate-live-weekly.yml"
_RUNGS = ("deterministic", "judge", "model")

# The GitHub Environment holding every provider secret. A1's approval boundary.
_ENVIRONMENT = "live"

# The markers selecting a graded layer. A gate step naming one of these is
# grading, whatever the step is called.
_GRADED_MARKERS = ("evaluator", "tool", "sec")

# The distribution name, as every install line spells it.
_HARNESS_PACKAGE = "ap-harness-qc"

# The resolved commit, as an expression reads it. A resolve job publishes it as
# a job output and the debug workflow as a step output, which is the same fact
# reaching the install line by the two routes Actions offers.
_RESOLVED_SHA = "outputs.harness_sha"

# The resolve job's green assessment, as a job condition reads it.
_GREEN = "outputs.green"

# The resolver, as a workflow invokes it. A job running this is the one whose
# refusal everything else must wait for.
_RESOLVER = "tools.harness_pin"

# The workflow exempt from the green gate, and the token by which it tolerates
# a refusal rather than being spared one.
_DEBUG = "debug-cases-on-demand.yml"
_TOLERATES = "|| true"

# The Actions status functions. Each one runs a job whose dependency FAILED,
# which is precisely how a job outruns a refusal. The implicit default is
# success(), so a condition naming none of these still waits.
_STATUS_FUNCTIONS = ("always(", "failure(", "cancelled(")


def _load(name: str) -> dict[str, Any]:
    """Return a parsed workflow definition.

    Args:
        name (str): The workflow filename.

    Returns:
        dict: The parsed document.
    """
    return yaml.safe_load((_WORKFLOWS / name).read_text(encoding="utf-8"))


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every step across every job.

    Args:
        workflow (dict): A parsed workflow.

    Returns:
        list[dict]: The steps, in document order.
    """
    return [
        step
        for job in (workflow.get("jobs") or {}).values()
        for step in (job.get("steps") or [])
    ]


def _jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return the workflow's jobs.

    Args:
        workflow (dict): A parsed workflow.

    Returns:
        dict: Job name to definition.
    """
    return workflow.get("jobs") or {}


def _needs(job: dict[str, Any]) -> list[str]:
    """Return the jobs one job depends on, however the key was written.

    Args:
        job (dict): A parsed job.

    Returns:
        list[str]: The named dependencies. A bare string is a list of one,
        which is what makes the two spellings indistinguishable to a reader
        and therefore worth normalizing here rather than at each call.
    """
    declared = job.get("needs") or []
    if isinstance(declared, str):
        return [declared]
    return list(declared)


def _provider_secrets(text: str) -> set[str]:
    """Return the provider secrets a workflow references.

    Args:
        text (str): The workflow source.

    Returns:
        set[str]: Secret names other than the automatic token. **The automatic
        token is not a provider credential**: it is scoped to this repository's
        own run and buys no quota anywhere.
    """
    named = set(re.findall(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text))
    return named - {"GITHUB_TOKEN"}


def _run_lines(job: dict[str, Any]) -> list[str]:
    """Return every shell command a job runs, one entry per step.

    Args:
        job (dict): A parsed job.

    Returns:
        list[str]: The ``run`` bodies, line continuations folded away so a
        flag and its value can be matched on one string.
    """
    bodies: list[str] = []
    for step in job.get("steps") or []:
        body = step.get("run")
        if body:
            bodies.append(re.sub(r"\\\s*", " ", str(body)))
    return bodies



def _selects_a_graded_marker(line: str) -> bool:
    """Report whether a command selects a graded marker with `-m`.

    **The marker has to be selected, not merely mentioned.** An earlier version
    asked whether the body contained "pytest" and any of the marker names as a
    bare substring, and a run body is one string per step including its shell
    comments. A note explaining an install said "toolchain" next to the word for
    the test runner, `tool` matched inside it, and `115702` reported the install
    step as an ungated graded invocation.

    **"sec" is the dangerous one**, being a substring of section, second,
    security and secret, all of which belong in a comment about a gate.

    Args:
        line (str): One step's run body, continuations already folded.

    Returns:
        bool: True where the body invokes pytest and a ``-m`` expression selects
        a graded marker as a whole word. **A computed expression selects
        nothing here**, which is unchanged: a dispatch passing a marker through
        an input never carried a literal one to match.
    """
    if "pytest" not in line:
        return False
    for quoted, bare in re.findall(r'-m\s+(?:"([^"]*)"|(\S+))', line):
        selected = quoted or bare
        if any(
            re.search(rf"\b{re.escape(marker)}\b", selected)
            for marker in _GRADED_MARKERS
        ):
            return True
    return False


def _graded_invocations(job: dict[str, Any]) -> list[str]:
    """Return the job's commands that execute a graded layer.

    Args:
        job (dict): A parsed job.

    Returns:
        list[str]: The pytest invocations selecting a graded marker.
    """
    return [line for line in _run_lines(job) if _selects_a_graded_marker(line)]


def _step_ids(job: dict[str, Any]) -> set[str]:
    """Return the identifiers of a job's steps.

    Args:
        job (dict): A parsed job.

    Returns:
        set[str]: Every declared step id.
    """
    return {
        str(step["id"]) for step in job.get("steps") or [] if step.get("id")
    }


def _reachable(jobs: dict[str, dict[str, Any]], start: str) -> set[str]:
    """Return every job one job depends on, transitively.

    Args:
        jobs (dict): The workflow's jobs.
        start (str): The job to walk back from.

    Returns:
        set[str]: The names reachable through ``needs``, excluding the start.
        **Transitive, because a guard one rung down still guards.** Requiring a
        direct dependency would force every job to name the resolve job whether
        or not it reads an output of it.
    """
    seen: set[str] = set()
    pending = list(_needs(jobs.get(start) or {}))
    while pending:
        name = pending.pop()
        if name in seen or name not in jobs:
            continue
        seen.add(name)
        pending.extend(_needs(jobs[name]))
    return seen


def _graded_or_gated(job: dict[str, Any]) -> bool:
    """Report whether a job executes any test at all.

    Args:
        job (dict): A parsed job.

    Returns:
        bool: True when a step invokes pytest. **Any layer counts**, not only
        the graded ones: a precondition run against an unestablished harness
        costs runner time and reports a result nobody can rely on.
    """
    return any("pytest" in line for line in _run_lines(job))


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCWorkflowProperties:
    """The debug workflow's exclusions, and what only it may do."""

    @allure.story("No verdict")
    def MQC_CAS_UNI_115700_the_debug_workflow_yields_no_verdict_and_gates_nothing(
        self,
    ) -> None:
        """A hand-typed selection is arbitrary and has no backstop.

        Three independent exclusions, because structural separation alone fails
        the day somebody widens the collector pattern, and marking alone fails
        if nobody filters on it.

        Returns:
            None
        """
        debug = _load("debug-cases-on-demand.yml")

        # Manual dispatch only. A debug run must not be reachable from a push.
        triggers = debug.get(True) or debug.get("on")
        assert set(triggers) == {"workflow_dispatch"}, (
            f"a debug run is dispatched deliberately and nothing else: {triggers}"
        )

        # Its artifact does not carry the collector prefix, so exclusion from
        # the durable record does not depend on a negative match.
        uploads = [
            step for step in _steps(debug)
            if str(step.get("uses", "")).startswith("actions/upload-artifact")
        ]
        assert uploads, "the run uploads nothing, so nothing can be inspected"
        for step in uploads:
            name = str((step.get("with") or {}).get("name", ""))
            assert not name.startswith(_COLLECTOR_PREFIX), (
                f"artifact {name!r} carries the collector prefix, so a debug "
                f"run would reach the durable record"
            )
            assert name.startswith("scratch-"), (
                f"artifact {name!r} should be visibly scratch"
            )

        # It says so, where a reader will see it.
        source = (_WORKFLOWS / "debug-cases-on-demand.yml").read_text(encoding="utf-8")
        assert "no verdict" in source.lower()

    @allure.story("Judging")
    def MQC_CAS_UNI_115701_only_the_debug_workflow_judges_a_failed_case(
        self,
    ) -> None:
        """The gate spends nothing on a case that has already failed.

        Invoking a judge on a failed case costs a request for information that
        changes no outcome, which is why skipping it is the default. **Debugging
        is the case where the information does change something**: the rubric
        separates a wrong case from a wrong model, and those prompt entirely
        different fixes.

        **A judged run in the gate spends nothing**, because ``--judge-mode``
        follows ``--mode`` and a replayed judge reads a stored judgement. A
        debug run passing ``--judge-mode live`` spends deliberately, against a
        named subset.

        Returns:
            None
        """
        judging = "--judge-on-failure"

        debug_source = (_WORKFLOWS / "debug-cases-on-demand.yml").read_text(
            encoding="utf-8"
        )
        assert judging in debug_source, (
            "the debug workflow exists to tell a wrong case from a wrong model, "
            "and the rubric is what does that"
        )

        for workflow in sorted(_WORKFLOWS.glob("*.yml")):
            if workflow.name == "debug-cases-on-demand.yml":
                continue
            assert judging not in workflow.read_text(encoding="utf-8"), (
                f"{workflow.name} judges a failed case, spending a request for "
                f"information that changes no outcome"
            )


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCAttributionLadder:
    """Each rung holds everything fixed except one thing.

    Designed in ``docs/design/consumer_ci.md`` section 7. A graded run has two
    moving parts, the candidate and the judge, and a job that moves both can
    only report that something changed.
    """

    @allure.story("The gate stays credential-free")
    def MQC_CAS_UNI_115702_a_graded_gate_job_that_needs_a_credential_is_reported(
        self,
    ) -> None:
        """The gate grades only because both sides are replayed.

        **This is the half of A1 that is structural rather than stated.** The
        gate names no environment and references no provider secret, so a
        graded step that needed one could not run here even if somebody added
        it, and the failure would arrive as a confusing authentication error
        rather than as this.

        **The flag matters as much as the secret.** ``--judge-mode`` follows
        ``--mode`` when absent, so a graded step is free precisely while it
        stays absent or says replay. A step passing ``--judge-mode live``
        reintroduces a judge call per passing case, which is the cost that kept
        grading out of the gate until judge fixtures existed.

        Returns:
            None
        """
        source = (_WORKFLOWS / _GATE).read_text(encoding="utf-8")
        gate = _load(_GATE)

        secrets_named = _provider_secrets(source)
        assert not secrets_named, (
            f"the gate references provider {sorted(secrets_named)}, so it can "
            f"spend quota on every push and A1's boundary is no longer "
            f"structural"
        )

        graded_jobs = {
            name: job for name, job in _jobs(gate).items()
            if _graded_invocations(job)
        }
        assert graded_jobs, (
            "the gate grades nothing, so the payoff of the judge fixture was "
            "designed and never taken (consumer_ci.md section 7.1)"
        )

        for name, job in graded_jobs.items():
            assert "environment" not in job, (
                f"job {name!r} grades from environment "
                f"{job.get('environment')!r}, which exists to hold secrets"
            )
            for line in _graded_invocations(job):
                assert "--mode replay" in line, (
                    f"job {name!r} grades without replaying the candidate, "
                    f"which spends quota on every push: {line.strip()}"
                )
                assert "--judge-mode live" not in line, (
                    f"job {name!r} judges live, one call per passing case, "
                    f"which is what kept grading out of the gate: {line.strip()}"
                )

    @allure.story("The ladder")
    def MQC_CAS_UNI_115703_a_live_job_that_does_not_follow_the_ladder_is_reported(
        self,
    ) -> None:
        """A red rung stops the ladder, and each rung moves one thing.

        **Sequence is the whole mechanism.** Running the judge live after our
        own code has already changed a frozen outcome spends quota to
        rediscover something established, and a run whose three jobs started
        together can say only that something moved.

        **Every rung that spends is named.** A live step outside an
        environment would run on a fork's pull request, so the environment is
        the approval boundary rather than a label.

        Returns:
            None
        """
        weekly = _load(_LIVE)
        jobs = _jobs(weekly)

        for name in _RUNGS:
            assert name in jobs, (
                f"rung {name!r} is missing, so the ladder cannot attribute "
                f"what it was built to attribute"
            )

        # EACH RUNG NEEDS THE ONE BELOW IT. Checked pairwise rather than by
        # reading the file top to bottom, because job order in the document
        # means nothing to Actions.
        for rung in range(1, len(_RUNGS)):
            lower, upper = _RUNGS[rung - 1], _RUNGS[rung]
            assert lower in _needs(jobs[upper]), (
                f"{upper!r} does not need {lower!r}, so it runs even when the "
                f"rung below it is red and spends quota to rediscover a known "
                f"break"
            )

        # RUNG 1 IS THE FREE ONE, here as in the gate.
        first = jobs[_RUNGS[0]]
        assert "environment" not in first, (
            f"the replayed rung names environment {first.get('environment')!r}, "
            f"so the precondition deciding whether to spend now needs approval "
            f"to answer"
        )
        for line in _graded_invocations(first):
            assert "--mode replay" in line and "--judge-mode live" not in line, (
                f"the first rung moves more than our own code: {line.strip()}"
            )

        # RUNG 2 MOVES THE JUDGE AND NOTHING ELSE.
        judged = _graded_invocations(jobs[_RUNGS[1]])
        assert judged, "the judge rung grades nothing"
        for line in judged:
            assert "--mode replay" in line, (
                f"the judge rung dispatches the candidate live, so a failure "
                f"no longer attributes to the judge: {line.strip()}"
            )
            assert "--judge-mode live" in line, (
                f"the judge rung replays the judge, which is rung 1 again at "
                f"the cost of a scheduled run: {line.strip()}"
            )

        # RUNG 3 MOVES EVERYTHING, which is the only rung that may.
        live = _graded_invocations(jobs[_RUNGS[2]])
        assert live, "the model rung grades nothing"
        for line in live:
            assert "--mode live" in line, (
                f"the model rung replays the candidate, so it reports nothing "
                f"about the model: {line.strip()}"
            )

        # EVERY SPENDING JOB IS GATED BY AN ENVIRONMENT, in every workflow that
        # has one, not only in this one.
        for workflow in sorted(_WORKFLOWS.glob("*.yml")):
            for name, job in _jobs(_load(workflow.name)).items():
                if not any("--mode live" in line for line in _run_lines(job)):
                    continue
                assert job.get("environment") == _ENVIRONMENT, (
                    f"{workflow.name} job {name!r} dispatches live outside the "
                    f"{_ENVIRONMENT!r} environment, so the secret it spends has "
                    f"no approval boundary"
                )


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCResolveObligation:
    """Who is obliged to call the resolver, as opposed to what it does.

    ``MQC_CAS_UNI_115300`` through ``115313`` cover the resolver itself. This
    covers the workflows' duty to use it, designed in
    ``docs/design/consumer_ci.md`` sections 3.1 and 7.6.
    """

    @allure.story("Install by resolved commit")
    def MQC_CAS_UNI_115704_a_workflow_installing_an_unresolved_harness_is_reported(
        self,
    ) -> None:
        """An unverified instrument attributes our defect to the model.

        **Section 3.1 step 3 was written as a property of the gate** because
        the gate was the only workflow at the time, and the weekly ladder was
        then written installing the harness without resolving it. This is
        written against the class instead: a case naming one workflow passes
        the moment a fourth is added with the same defect.

        **The argument is strongest where it was missing.** A gate running
        against a red harness wastes runner time. A live run spends provider
        quota, and its findings are attributed to a third party.

        Returns:
            None
        """
        installs = 0
        for workflow in sorted(_WORKFLOWS.glob("*.yml")):
            jobs = _jobs(_load(workflow.name))
            for name, job in jobs.items():
                for line in _run_lines(job):
                    if _HARNESS_PACKAGE not in line:
                        continue
                    installs += 1
                    self._assert_resolved(workflow.name, name, jobs, line)

        assert installs, (
            "no workflow installs the harness, so this check establishes "
            "nothing and the obligation it states is unenforced"
        )

    @allure.story("Spending waits for green")
    def MQC_CAS_UNI_115705_a_spending_workflow_that_skips_the_green_gate_is_reported(
        self,
    ) -> None:
        """A red pairing stops a spending ladder before its first rung.

        **An ungated gate run still yields a marked artifact**, because a free
        run producing a marked result costs nothing. An ungated live run has
        nothing to offer in exchange for the quota, so it does not start.

        Returns:
            None
        """
        for workflow in sorted(_WORKFLOWS.glob("*.yml")):
            jobs = _jobs(_load(workflow.name))
            spending = {
                name for name, job in jobs.items()
                if any("--mode live" in line for line in _run_lines(job))
            }
            if not spending:
                continue

            guards = {
                name for name, job in jobs.items()
                if _GREEN in str(job.get("if", ""))
            }
            assert guards, (
                f"{workflow.name} dispatches live and no job waits on the "
                f"pairing being green, so quota is spent measuring a model "
                f"with an instrument nobody verified"
            )
            for name in spending:
                assert guards & (_reachable(jobs, name) | {name}), (
                    f"{workflow.name} job {name!r} spends without any guarded "
                    f"job above it, so the green check it inherits is none"
                )

    @staticmethod
    def _assert_resolved(
        workflow: str,
        job_name: str,
        jobs: dict[str, Any],
        line: str,
    ) -> None:
        """Report an install taking anything other than a resolved commit.

        Args:
            workflow (str): The workflow filename, for the message.
            job_name (str): The installing job.
            jobs (dict): Every job in that workflow.
            line (str): The install command.

        Returns:
            None
        """
        assert _RESOLVED_SHA in line, (
            f"{workflow} job {job_name!r} installs the harness without a "
            f"resolved commit, so pip takes whatever the branch head is at "
            f"install time: {line.strip()}"
        )

        # THE SHA REACHES THE LINE BY ONE OF TWO ROUTES, and each has to lead
        # somewhere that exists. An expression naming a job or step that is not
        # there expands to empty, and the install then pins nothing at all.
        for producer in re.findall(r"needs\.([A-Za-z0-9_-]+)\." + re.escape(_RESOLVED_SHA), line):
            assert producer in _needs(jobs[job_name]), (
                f"{workflow} job {job_name!r} reads an output of "
                f"{producer!r} without needing it, so it expands to empty"
            )
            declared = (jobs.get(producer) or {}).get("outputs") or {}
            assert "harness_sha" in declared, (
                f"{workflow} job {producer!r} publishes no harness_sha"
            )

        for producer in re.findall(r"steps\.([A-Za-z0-9_-]+)\." + re.escape(_RESOLVED_SHA), line):
            assert producer in _step_ids(jobs[job_name]), (
                f"{workflow} job {job_name!r} reads step {producer!r}, which "
                f"it does not contain, so the pin expands to empty"
            )


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCArtifactContract:
    """The downstream artifact contract, against what the workflows run."""

    @allure.story("Both mandated artifacts are emitted")
    def MQC_CAS_UNI_115708_a_workflow_emitting_one_mandated_artifact_is_reported(
        self,
    ) -> None:
        """Every workflow invocation writing an artifact writes both of them.

        ``testing-standards.md`` section 5 mandates JUnit XML and Allure raw
        results together, and they are read by different people: JUnit for
        triaging a failure, Allure for the report readiness is judged from. An
        invocation naming ``--out-dir`` satisfies both, since the flag derives
        each destination.

        **The scanner is the harness's and is called with this root.** The
        harness owns no case data and this repository owns its workflows, so
        ``MQC_CMN_UNI_112525`` calls the same function with the other one.

        Design: ``consumer_ci.md`` section 4.12.

        Returns:
            None
        """
        gaps = artifact_mandate_gaps(Path(__file__).resolve().parents[2])

        assert not gaps, (
            "workflow invocations emit one of the two mandated artifacts, so "
            "the run produces no report to judge readiness from: "
            + "; ".join(gaps)
        )


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCRefusalReachesTheRun:
    """A refusal is worth what the workflows do with it.

    ``MQC_CAS_UNI_115313`` establishes that the resolver refuses. These
    establish that a refusal stops a regression run and does not stop a debug
    run, designed in ``docs/design/consumer_ci.md`` section 3.9.
    """

    @allure.story("A refusal stops the run")
    def MQC_CAS_UNI_115706_a_test_executing_job_that_outruns_a_refusal_is_reported(
        self,
    ) -> None:
        """Exit 4 is only a refusal if something declines to run.

        **The mechanism is the dependency graph, not the exit code.** A job
        carrying a status function runs when the resolver failed, and a job
        that never named the resolver in its ``needs`` never waited for it.
        Either way a full regression executes against a harness whose own gate
        is red, and every finding is attributed to the model under test.

        **Job-level and step-level conditions are different questions.** A step
        saying ``always()`` inside a job that needs the resolver is correct and
        common: it makes Gate 3 report even when Gate 2 failed, within a job
        that would not have started had the resolver refused. Only a job-level
        status function can outrun a refusal, so only those are read here.

        Returns:
            None
        """
        checked = 0
        for workflow in sorted(_WORKFLOWS.glob("*.yml")):
            if workflow.name == _DEBUG:
                continue
            jobs = _jobs(_load(workflow.name))
            resolvers = {
                name for name, job in jobs.items()
                if any(_RESOLVER in line for line in _run_lines(job))
            }
            if not resolvers:
                continue

            for name, job in jobs.items():
                if name in resolvers or not _graded_or_gated(job):
                    continue
                checked += 1

                assert resolvers & _reachable(jobs, name), (
                    f"{workflow.name} job {name!r} runs tests without waiting "
                    f"on the resolver, so a red harness costs a full run"
                )

                condition = str(job.get("if", ""))
                outran = [
                    token for token in _STATUS_FUNCTIONS if token in condition
                ]
                # A STATUS FUNCTION ALONE OUTRUNS THE REFUSAL, and one paired
                # with a requirement that an upstream job SUCCEEDED does not: a
                # refused resolver leaves that job skipped, and skipped is not
                # success. Equality is the point, since `!= 'failure'` admits
                # exactly the skipped state a refusal produces. Design section
                # 3.9.3.
                guarded = any(
                    f"needs.{upstream}.result == 'success'" in condition
                    or f'needs.{upstream}.result == "success"' in condition
                    for upstream in _needs(job)
                )
                assert not outran or guarded, (
                    f"{workflow.name} job {name!r} carries {outran} at job "
                    f"level with nothing requiring an upstream job to have "
                    f"succeeded, so it starts although the resolver refused: "
                    f"{condition}"
                )

        assert checked, (
            "no workflow pairs a resolver with a test-executing job, so this "
            "check establishes nothing"
        )

    @allure.story("Development is exempt")
    def MQC_CAS_UNI_115707_a_debug_workflow_blocked_by_a_red_harness_is_reported(
        self,
    ) -> None:
        """Withholding the tool when it is needed is the failure here.

        Stabilization and expansion happen against a harness branch in
        development, which is red as a matter of course rather than as a
        fault. **Refusing to debug against it would withhold the tool exactly
        when it is needed**, so the debug workflow tolerates a refusal instead
        of being spared one: the resolver is allowed to fail without failing
        the step.

        Two facts make that safe together, and neither alone: the run records
        what it used, and it yields no verdict.

        Returns:
            None
        """
        jobs = _jobs(_load(_DEBUG))
        source = (_WORKFLOWS / _DEBUG).read_text(encoding="utf-8")

        resolving = [
            line for job in jobs.values() for line in _run_lines(job)
            if _RESOLVER in line
        ]
        assert resolving, f"{_DEBUG} resolves nothing, so it pins nothing"
        for line in resolving:
            assert _TOLERATES in line, (
                f"{_DEBUG} lets the resolver fail the step, so a red harness "
                f"withholds the tool exactly when it is needed: {line.strip()}"
            )

        for name, job in jobs.items():
            assert _GREEN not in str(job.get("if", "")), (
                f"{_DEBUG} job {name!r} waits for a green harness, which "
                f"blocks debugging while the harness is being stabilized"
            )

        assert "GREEN GATE DOES NOT APPLY" in source, (
            f"{_DEBUG} no longer says why it is exempt, so the next reader "
            f"sees an omission rather than a decision"
        )
