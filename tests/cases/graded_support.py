# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""What every graded case does, written once.

**Not collected.** The filename carries no ``mqc_`` prefix, so ``pytest.ini``
never sees it, which is the same device ``provider_doubles.py`` uses in the
harness. A graded case is a test; the machinery underneath one is not.

Every graded case is the same four steps against different data: find its pair
in the shipped corpus, dispatch it, evaluate what came back, and assert the
verdict. **Writing that once means a case reads as its own claim** rather than
as sixty repetitions of a loop.

**Dispatch honours the run's mode.** ``--mode replay`` reads a recorded
fixture and spends nothing; ``--mode live`` calls the provider, paced by the
spacing in ``config/engines.yaml``. Neither is chosen here: the invocation
decides, and a case cannot quietly spend quota.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pytest

from cmn.config import load_engines
from cmn.options import resolve_judge_mode
from evaluation.isolation import UnauthoredMaterial
from evaluation.judge import JudgeBinding
from evaluation.pipeline import ObservationContext, evaluate_observation
from execution.dispatch import DispatchPlan, DispatchSession, dispatch_case
from execution.judge_channel import JudgementPlan, judge_channel_from_roster
from ingestion.cases import build_evaluation_cases
from ingestion.loaders import load_rule_sets_from_yaml, load_tasks_from_yaml

# Recorded responses live beside the corpus they answer, in the repository that
# owns the data. The harness owns none of it.
FIXTURE_ROOT = "tests/fixtures/replay"


def repository_root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``data/``.
    """
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def shipped_cases() -> dict[str, Any]:
    """Return every evaluation case the shipped corpus defines.

    **Cached, because every graded case asks for it.** Loading 51 tasks and 51
    rule sets once per test would dominate a replay run's wall clock without
    changing a single result.

    Returns:
        dict[str, Any]: Case identifier to :class:`EvaluationCase`.
    """
    root = repository_root()
    tasks: list[Any] = []
    rules: list[Any] = []
    for source in sorted((root / "data" / "tasks").glob("*.yaml")):
        tasks.extend(load_tasks_from_yaml(source))
    for source in sorted((root / "data" / "rules").glob("*.yaml")):
        rules.extend(load_rule_sets_from_yaml(source))
    return {case.case_id: case for case in build_evaluation_cases(tasks, rules)}



@lru_cache(maxsize=1)
def engine_roster() -> dict[str, Any]:
    """Return the engine roster, which carries each engine's pacing.

    **Read from the harness rather than restated here.** Spacing is a property
    of a provider's free tier, not of this corpus, and a second copy would
    drift toward whichever repository was edited last.

    Returns:
        dict[str, Any]: Engine name to its configuration.
    """
    return load_engines(
        repository_root().parent / "AP-Harness-QC" / "config" / "engines.yaml"
    )


def case_for(task_id: str, rule_id: str) -> Any:
    """Return one shipped case by the pair that defines it.

    Args:
        task_id (str): The task.
        rule_id (str): The rule set judging it.

    Returns:
        Any: The :class:`EvaluationCase`.

    Raises:
        KeyError: Naming the pair, when the corpus carries no such case. **A
            graded case naming a pair that does not exist would otherwise
            report a harness error**, which reads as our defect rather than a
            typo in the test.
    """
    identifier = f"{task_id}::{rule_id}"
    cases = shipped_cases()
    if identifier not in cases:
        raise KeyError(
            f"{identifier} is not in the shipped corpus; the graded case names "
            f"a task and rule pair that data/ does not define"
        )
    return cases[identifier]


def dispatch_plan(config: Any) -> DispatchPlan:
    """Return the dispatch configuration this invocation asked for.

    **The invocation decides, never the case.** A case that chose live mode
    could spend quota on a pull request, which is the whole reason ``--mode``
    defaults to replay.

    Args:
        config (Any): pytest's configuration.

    Returns:
        DispatchPlan: Mode, fixture location, whether to record, and whether to
        hold the provider connection between cases, and whether to dispatch
        only observations not already recorded. **Both default off**: each case
        is isolated from the one before it without asking, and `--mode live`
        means call the provider (harness sections 7.7 and 7.10).
    """
    engine = config.getoption("--engine")
    roster = engine_roster()
    return DispatchPlan(
        mode=config.getoption("--mode"),
        fixture_root=repository_root() / FIXTURE_ROOT,
        model=roster[engine].model if engine in roster else None,
        record=bool(config.getoption("--mode") == "live"),
        keep_connection=bool(config.getoption("--keep-connection")),
        fill_gaps=bool(config.getoption("--fill-gaps")),
    )


def dispatch_session(config: Any) -> DispatchSession:
    """Return run-level pacing state, configured from the engine roster.

    **Spacing is per engine because free-tier ceilings differ.** A session
    built without it would issue every request at once and be rate limited
    into a run that measures the limiter rather than the model.

    Args:
        config (Any): pytest's configuration.

    Returns:
        DispatchSession: Pacing and circuit-breaker state.
    """
    engine = config.getoption("--engine")
    roster = engine_roster()
    spacing = roster[engine].spacing_sec if engine in roster else 0.0
    return DispatchSession(spacing_sec=spacing)



def harness_root() -> Path:
    """Return the harness checkout, which owns the engine roster.

    Returns:
        Path: The sibling directory holding ``config/engines.yaml``.
    """
    return repository_root().parent / "AP-Harness-QC"


def judgement_plan(config: Any) -> JudgementPlan:
    """Return how this invocation obtains judgements.

    **`--judge-mode` defaults to `--mode`** and the incoherent quadrant is
    refused at parsing, which `resolve_judge_mode` already does (harness
    ``tier3_evaluation.md`` section 5A.5).

    **This is the difference between a free pull request and a quota bill.**
    `FixtureKey` keys the candidate only, so a bound judge is a live call
    whatever `--mode` says; a replay run that judged live would spend provider
    quota on every pull request.

    Args:
        config (Any): pytest's configuration.

    Returns:
        JudgementPlan: Mode, where judgements are stored, and whether to
        record. **Recording follows live mode**, as it does for candidates.
    """
    mode = config.getoption("--mode")
    resolved = resolve_judge_mode(mode, config.getoption("--judge-mode") or "")
    return JudgementPlan(
        mode=resolved,
        fixture_root=repository_root() / FIXTURE_ROOT,
        record=bool(resolved == "live"),
    )


@lru_cache(maxsize=8)
def _channel(engine: str, mode: str, record: bool, keep: bool) -> Any:
    """Return one judge channel, built once per distinct configuration.

    **Cached because pacing is per channel.** A fresh channel per case would
    reset `last_request_at` and defeat the spacing the free tier requires,
    which is the same reason `DispatchSession` outlives one dispatch.

    Args:
        engine (str): The judge engine, empty for the configured primary.
        mode (str): The resolved judge mode.
        record (bool): Whether to store what is obtained.
        keep (bool): Whether to hold the connection between judgements.

    Returns:
        Any: The :class:`JudgeChannel`.
    """
    return judge_channel_from_roster(
        harness_root() / "config" / "engines.yaml",
        engine or None,
        keep_connection=keep,
        plan=JudgementPlan(
            mode=mode,
            fixture_root=repository_root() / FIXTURE_ROOT,
            record=record,
        ),
    )


def judge_binding(config: Any, candidate_engine: str) -> Any:
    """Return the judge that decides, which is the only judge there is.

    **One judge, by scope.** A3.2 records why: divergence between judges is a
    finding about judges, and acting on it needs a judge over the judges, which
    does not bottom out. What checks this one is calibration against exemplars,
    whose levels were authored and are therefore known-correct.

    Args:
        config (Any): pytest's configuration.
        candidate_engine (str): Which engine produced the response, recorded so
            that self-preference is a comparison rather than a guess.

    Returns:
        Any: The :class:`JudgeBinding`.
    """
    plan = judgement_plan(config)
    channel = _channel(
        "", plan.mode, plan.record, bool(config.getoption("--keep-connection"))
    )
    return JudgeBinding(
        invoke=channel.invoke,
        judge_engine=channel.engine,
        candidate_engine=candidate_engine,
    )

def observe(
    config: Any,
    task_id: str,
    rule_id: str,
    *,
    observation_index: int = 0,
    judge: Optional[Any] = None,
) -> Any:
    """Dispatch one shipped case and evaluate what came back.

    Args:
        config (Any): pytest's configuration, carrying the invocation.
        task_id (str): The task to send.
        rule_id (str): The rule set judging it.
        observation_index (int): Which repeat observation this is (A4).
        judge (Optional[Any]): Overrides the configured judge. **Absent is
            the normal case**: a rule carrying a rubric gets the roster's
            judge, and one carrying none gets no judge at all, which is what
            the deterministic families rely on.

    Returns:
        Any: The :class:`EvaluationResult`.
    """
    case = case_for(task_id, rule_id)
    outcome = dispatch_case(
        case,
        config.getoption("--engine"),
        dispatch_plan(config),
        dispatch_session(config),
        observation_index=observation_index,
    )

    # A HARNESS EVENT IS A SKIP, NEVER A FAILURE. `framework-rules.md`
    # section 4: a QC_HARNESS_* code says our infrastructure did not produce a
    # measurement, and recording that as a red case would assert something
    # about a model that was never asked. A missing fixture is the common one
    # before a corpus has been recorded.
    if outcome.taxonomy_code and outcome.taxonomy_code.startswith("QC_HARNESS_"):
        pytest.skip(f"{outcome.taxonomy_code}: {case.case_id} produced no measurement")

    task = case.task
    context = ObservationContext(
        case_id=case.case_id,
        rules=case.golden_rules,
        material=UnauthoredMaterial(
            candidate_output=outcome.response.text if outcome.response else "",
            task_instruction=task.user_prompt,
            context_documents={
                document.document_id: document.content
                for document in task.context_documents
            },
        ),
        declared_adversarial=task.contains_adversarial_content,
        observation_index=observation_index,
        produced_output=bool(
            outcome.response
            and (outcome.response.text or outcome.response.tool_calls)
        ),
        tool_calls=tuple(outcome.response.tool_calls) if outcome.response else (),
        offered_tools=tuple(task.available_tools),
    )

    # A JUDGE IS BOUND ONLY WHERE THERE IS SOMETHING TO JUDGE. A rule carrying
    # no rubric is not judged (harness section 5A.6), and the deterministic
    # families carry none: binding one for them would build a channel, resolve
    # a credential and pace a request that nothing would ever send.
    if judge is None and case.golden_rules.rubric is not None:
        judge = judge_binding(config, config.getoption("--engine"))

    return evaluate_observation(context, judge)



def observation_count(config: Any) -> int:
    """Return how many times each case is observed.

    **Three by default, from the engine roster** (A4.1). The count is a
    property of the run rather than of a case: a case cannot decide to be
    sampled more often than the quota allows.

    Args:
        config (Any): pytest's configuration.

    Returns:
        int: The count, at least one. ``--observations`` overrides it, which
        `cmn_verdict_and_cli.md` marks a **manual selection**: a run that
        samples differently from the configured standard yields no verdict.
    """
    override = int(config.getoption("--observations") or 0)
    if override > 0:
        return override
    engine = config.getoption("--engine")
    roster = engine_roster()
    configured = getattr(roster.get(engine), "observations", 0) if engine in roster else 0
    return max(1, int(configured or 1))


def observe_repeatedly(
    config: Any,
    task_id: str,
    rule_id: str,
    *,
    judge: Optional[Any] = None,
) -> list[Any]:
    """Observe one case every configured time and return every result.

    **A4.1: three observations, because inconsistency is a model defect.** A
    model that answers one question three ways has one, and that defect is not
    confined to the case exposing it: every single-sample result from the same
    model becomes a draw from a distribution nobody characterised.

    **Every observation is dispatched, even after one fails.** Stopping early
    would hide the disagreement, which is the finding.

    Args:
        config (Any): pytest's configuration, carrying the invocation.
        task_id (str): The task to send.
        rule_id (str): The rule set judging it.
        judge (Optional[Any]): Overrides the configured judge.

    Returns:
        list: One :class:`EvaluationResult` per observation, in index order.
        **Never empty**, the count being at least one.
    """
    return [
        observe(config, task_id, rule_id, observation_index=index, judge=judge)
        for index in range(observation_count(config))
    ]


def consistent(results: list[Any]) -> Optional[str]:
    """Return why repeat observations disagreed, or ``None`` when they agree.

    **No majority is taken.** Two passes and a fail is not a pass: a majority
    discards exactly the finding the repeats exist to produce, which is that
    this model does not reliably do this (harness section 4.9.1).

    Args:
        results (list): One result per observation.

    Returns:
        Optional[str]: A message naming what disagreed, or ``None``. **A single
        observation always agrees with itself**, which is honest rather than a
        false negative: with one sample there is nothing to compare.
    """
    if len(results) < 2:
        return None
    outcomes = {bool(entry.passed) for entry in results}
    if len(outcomes) == 1:
        return None
    passing = sum(1 for entry in results if entry.passed)
    return (
        f"QC_LLM_INCONSISTENT: {passing} of {len(results)} observations "
        f"passed, so the model does not answer this consistently and no "
        f"single-sample result from it characterises anything"
    )

def failure_detail(result: Any) -> str:
    """Return what failed, so a finding names its own cause.

    **Written once because five families ask the same question.** Each graded
    module previously carried its own copy, which pylint reported as
    duplication and which would have drifted the first time one was improved.

    **The detail is quoted, which is safe for every family that calls this.**
    A failing case here carries no adversarial payload, so the assertion text
    may repeat what the evaluator found, and that is what makes a failure
    diagnosable without opening an artifact.

    **The security suite deliberately does not use this.** Its own explainer
    prints identifiers and taxonomy codes and never the payload, because a
    failing security case is exactly where candidate output and a planted
    instruction would otherwise reach a log.

    Args:
        result (Any): The :class:`EvaluationResult`.

    Returns:
        str: The failing assertions and what each one found; failing that, the
        rubric verdict; failing that, why neither exists.
    """
    failures = [
        f"{entry.assertion_id} ({entry.taxonomy_code}): {entry.detail}"
        for entry in result.assertion_results
        if not entry.passed
    ]
    if failures:
        return "; ".join(failures)
    if result.score is not None:
        return (
            f"every assertion passed and the rubric scored "
            f"{result.score.value} against a threshold it did not clear"
        )
    return (
        f"no assertion failed and no score was produced: "
        f"judged={result.judged}, skipped={result.judge_skipped_reason}"
    )


def assert_consistent_pass(results: list[Any], explain: Any = None) -> Any:
    """Refuse disagreement, then refuse failure, and return the first result.

    **Written once because every graded case asks the same two questions.**
    The block was pasted into 54 cases before this existed, which pylint
    reported as duplication and which would have drifted the first time one
    copy was improved.

    **Consistency is checked first, and that order is deliberate.** A case
    whose observations disagree has already told us the model is unreliable;
    reporting instead that observation zero failed would name the symptom and
    hide the finding (harness section 4.9.1).

    Args:
        results (list): One result per observation, from
            :func:`observe_repeatedly`.
        explain (Any): How to describe a failure, defaulting to
            :func:`failure_detail`. The security suite passes its own, which
            never quotes a payload.

    Returns:
        Any: The first :class:`EvaluationResult`, for a case that wants to
        assert something further.

    Raises:
        AssertionError: When the observations disagree, or when they agree and
            failed.
    """
    disagreement = consistent(results)
    assert not disagreement, disagreement
    describe = explain or failure_detail
    assert results[0].passed, describe(results[0])
    return results[0]


def redacted_detail(result: Any, lead: str) -> str:
    """Return which assertions failed, and never what the model said.

    **The counterpart to :func:`failure_detail`, and the difference is the
    payload.** That one quotes what the evaluator found, which is right for
    every family whose material is ordinary. A security case carries a planted
    instruction and a response that may contain it, so the assertion message is
    the last place either should appear.

    **Written once because four security modules ask the same question.** Each
    carried its own copy, differing only in the lead-in, which pylint reported
    as duplication and which would have drifted the first time one was improved.

    Args:
        result (Any): The :class:`EvaluationResult`.
        lead (str): What the failure means, supplied by the calling module:
            the model disclosed, complied, substituted or invoked. **The lead is
            the only thing that varies**, which is why it is the only parameter.

    Returns:
        str: The failing assertion identifiers and their taxonomy codes, behind
        the lead. **No candidate output and no payload**, ever.
    """
    failures = [
        f"{entry.assertion_id} ({entry.taxonomy_code})"
        for entry in result.assertion_results
        if not entry.passed
    ]
    if not failures:
        return (
            f"no assertion failed, so the case did not pass for another reason: "
            f"judged={result.judged}, skipped={result.judge_skipped_reason}"
        )
    return f"{lead}: " + "; ".join(failures)
