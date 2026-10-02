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
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pytest

from cmn.observations import further_observations
from cmn.config import (
    load_engines,
    packaged_config_root,
    packaged_roster_path,
)
from cmn.options import resolve_judge_mode
from cmn.pricing import load_price_table
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
@lru_cache(maxsize=1)
def shipped_corpus() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return every shipped task and rule set, loaded once.

    **The one place the corpus files are walked.** Three callers had their own
    copy of this loop until 2026-10-01: this module's :func:`shipped_cases`, and
    a fixture in each of two unit modules. Pylint's duplication gate caught the
    third as it was written.

    **Tuples rather than lists, because the result is cached.** A caller that
    appended to a shared list would change what every later caller sees, and the
    callers here are tests.

    Returns:
        tuple: Every task, then every rule set.
    """
    root = repository_root()
    tasks: list[Any] = []
    rules: list[Any] = []
    for source in sorted((root / "data" / "tasks").glob("*.yaml")):
        tasks.extend(load_tasks_from_yaml(source))
    for source in sorted((root / "data" / "rules").glob("*.yaml")):
        rules.extend(load_rule_sets_from_yaml(source))
    return tuple(tasks), tuple(rules)


def shipped_cases() -> dict[str, Any]:
    """Return every evaluation case the shipped corpus defines.

    **Cached, because every graded case asks for it.** Loading 51 tasks and 51
    rule sets once per test would dominate a replay run's wall clock without
    changing a single result.

    Returns:
        dict[str, Any]: Case identifier to :class:`EvaluationCase`.
    """
    tasks, rules = shipped_corpus()
    return {
        case.case_id: case
        for case in build_evaluation_cases(list(tasks), list(rules))
    }



@lru_cache(maxsize=1)
def engine_roster() -> dict[str, Any]:
    """Return the engine roster, which carries each engine's pacing.

    **Read from the harness rather than restated here.** The roster carries
    evidence, not preferences: which spacing was measured, which model was
    retired and why, which engine grades. A second copy would drift toward
    whichever repository was edited last.

    **Asked of the installed harness, not of the directory beside this one.**
    This read `../AP-Harness-QC/config/engines.yaml`, which is true only on a
    disk where both repositories are checked out side by side. CI installs the
    pinned harness from git, so the path did not exist, an absent file loaded
    as an empty mapping, and Gate 4 failed with `judge engine 'gemini' is not
    on the roster` — a misconfigured instrument, reported three layers from its
    cause.

    Returns:
        dict[str, Any]: Engine name to its configuration.
    """
    return load_engines(packaged_roster_path())


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
    """Return run-level pacing state and spending state, from the roster and flags.

    **Spacing is per engine because free-tier ceilings differ.** A session built
    without it would issue every request at once and be rate limited into a run
    that measures the limiter rather than the model.

    **The ceiling arrives here or nowhere.** `--max-spend` was declared as an
    option, the session carried the field, and the refusal was written and
    tested, while this function read only the spacing: the ceiling was
    unreachable from a command line. A cap nobody can set is not a cap.

    **The price table comes with it**, because a ceiling without rates cannot be
    computed, and an uncomputable ceiling stops a budgeted run rather than
    pretending to hold (harness `MQC_EXE_UNI_10303`).

    Args:
        config (Any): pytest's configuration.

    Returns:
        DispatchSession: Pacing, circuit-breaker and spending state. **The table
        is loaded only where a ceiling is set**, so a replay gate neither reads
        the file nor prices anything it did not pay for.
    """
    engine = config.getoption("--engine")
    roster = engine_roster()
    spacing = roster[engine].spacing_sec if engine in roster else 0.0

    ceiling = float(config.getoption("--max-spend") or 0.0)
    if ceiling <= 0:
        return DispatchSession(spacing_sec=spacing)

    return DispatchSession(
        spacing_sec=spacing,
        max_spend=ceiling,
        prices=load_price_table(packaged_config_root() / "pricing.yaml"),
        # THE RUN'S OWN DATE, read once here rather than per response. A run
        # spanning midnight prices every request the same way, which is what
        # makes two readings of one corpus agree.
        priced_on=date.today(),
    )



def judgement_plan(config: Any, candidate_engine: str) -> JudgementPlan:
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
        candidate_engine (str): Which engine produced what is being graded.
            **Half the judgement's identity**, so it addresses the fixture: a
            plan naming a fixture root without it is refused by the harness,
            because one file would be shared by every engine (harness
            ``tier2_execution.md`` section 7.9.3).

    Returns:
        JudgementPlan: Mode, where judgements are stored, and whether to
        record. **Recording follows live mode**, as it does for candidates.
    """
    mode = config.getoption("--mode")
    resolved = resolve_judge_mode(mode, config.getoption("--judge-mode") or "")
    return JudgementPlan(
        mode=resolved,
        fixture_root=repository_root() / FIXTURE_ROOT,
        candidate_engine=candidate_engine,
        record=bool(resolved == "live"),
        # THE SAME FLAG THE CANDIDATE PLAN TAKES. Without it a run that
        # needed two judgements re-judged every one of them.
        fill_gaps=bool(config.getoption("--fill-gaps")),
    )


@lru_cache(maxsize=8)
def _channel(
    engine: str,
    mode: str,
    record: bool,
    keep: bool,
    fill: bool = False,
    candidate: str = "",
) -> Any:
    """Return one judge channel, built once per distinct configuration.

    **Cached because pacing is per channel.** A fresh channel per case would
    reset `last_request_at` and defeat the spacing the free tier requires,
    which is the same reason `DispatchSession` outlives one dispatch.

    Args:
        engine (str): The judge engine, empty for the configured primary.
        mode (str): The resolved judge mode.
        record (bool): Whether to store what is obtained.
        keep (bool): Whether to hold the connection between judgements.
        fill (bool): Whether to replay a judgement already recorded rather
            than asking again. **Part of the cache key**, because two
            channels differing only in this are different configurations.
        candidate (str): Which engine produced what is graded. **Part of the
            cache key for the same reason**, and the reason is sharper here:
            a channel cached under one candidate and handed to a run grading
            another would address the first engine's judgement files, which is
            the collision section 7.9.3 of the harness design records.

    Returns:
        Any: The :class:`JudgeChannel`.
    """
    return judge_channel_from_roster(
        packaged_roster_path(),
        engine or None,
        keep_connection=keep,
        plan=JudgementPlan(
            mode=mode,
            fixture_root=repository_root() / FIXTURE_ROOT,
            candidate_engine=candidate or engine or None,
            record=record,
            # THE PLAN THAT REACHES THE CHANNEL. `judgement_plan` builds
            # another one, read for its mode and record flag; setting the
            # flag only there left the channel filling nothing.
            fill_gaps=fill,
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
    plan = judgement_plan(config, candidate_engine)
    channel = _channel(
        "",
        plan.mode,
        plan.record,
        bool(config.getoption("--keep-connection")),
        plan.fill_gaps,
        candidate_engine,
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
        # WHAT THE PROVIDER SAID WHEN IT DECLINED, carried so the pipeline can
        # tell an affirmative refusal from an empty answer. For a declared
        # adversarial case the first is resistance and the second is not
        # (harness tier3_evaluation.md section 4.2.2).
        blocked_by=outcome.response.block_reason if outcome.response else "",
        blocked_at=outcome.response.block_stage if outcome.response else "",
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

    **And a single disagreement earns two more.** Three observations put a case
    at 0, 33, 67 or 100 percent disagreement, and only the 33 is worth refining:
    at five, one disagreement reads as a fifth and three as three fifths, which
    are different findings although both fail. The rule is the harness's
    (`cmn.observations.further_observations`) and this loop only dispatches what
    it asks for, per design section 4.9.2.2.

    Args:
        config (Any): pytest's configuration, carrying the invocation.
        task_id (str): The task to send.
        rule_id (str): The rule set judging it.
        judge (Optional[Any]): Overrides the configured judge.

    Returns:
        list: One :class:`EvaluationResult` per observation, in index order.
        **Never empty**, the count being at least one, and longer than the
        configured count where a disagreement earned more.
    """
    results = [
        observe(config, task_id, rule_id, observation_index=index, judge=judge)
        for index in range(observation_count(config))
    ]

    # ESCALATION IS THE HARNESS'S RULE AND THIS LOOP DECIDES NOTHING, which is
    # the boundary in CLAUDE.md: the cases own no harness code. Design section
    # 4.9.2.2.
    extra = further_observations([bool(entry.passed) for entry in results])
    taken = len(results)
    results += [
        observe(config, task_id, rule_id, observation_index=taken + offset, judge=judge)
        for offset in range(extra)
    ]
    return results


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
