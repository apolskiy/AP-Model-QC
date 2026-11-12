# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code that dispatches and evaluates a graded case, written once for every case.

Created: 2026-09-25
Last updated: 2026-11-11

This file contains ``observe``, which dispatches one shipped case, evaluates the
response with the harness's ``evaluate_observation`` and records it, and
``observe_repeatedly``, which does so ``observation_count`` times. Beside them sit the
corpus readers (``shipped_corpus``, ``shipped_cases``, ``case_for``, ``task_material``),
the run's plans (``dispatch_plan``, ``dispatch_session``, ``judgement_plan``,
``judge_binding``), ``judge_stopped``, ``quarantined_cases``, and the suite
readers ``case_rules_from_suite`` and ``case_families_from_suite``. The fields
an observation records are built in ``observation_records``.

**Every graded case calls ``observe_repeatedly``** and hands the results to
``consistency_support``, which decides it, so **a case reads as its own claim** rather
than as sixty repetitions of a loop. The readers also serve the ``mqc_uni_*``
preconditions and the case index, quarantine and ticket scripts in ``tools/``, so all
of them read the corpus one way.

**Not collected**, as the filename carries no ``mqc_`` prefix, the same device
``provider_doubles.py`` uses in the harness. A case is a test; its machinery is not.

**Dispatch honours the run's mode.** ``--mode replay`` reads a recorded
fixture and spends nothing; ``--mode live`` calls the provider, paced by the
spacing in ``config/engines.yaml``. Neither is chosen here: the invocation
decides, and a case cannot quietly spend quota.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Optional

import pytest

from cmn.observations import further_observations
from cmn.steps import entering
from cmn.pytest_support import corpus_selection
from cmn.config import (
    load_quarantine_for,
    load_engines,
    packaged_config_root,
    packaged_roster_path,
)
from cmn.emission import record_observation
from cmn.observations import assemble_observation
from cmn.options import resolve_judge_mode
from cmn.pricing import load_price_table
from cmn.prerequisites import record_rule_set_hash
from cmn.project_clock import project_today
from evaluation.isolation import UnauthoredMaterial
from evaluation.judge import JudgeBinding
from evaluation.pipeline import ObservationContext, evaluate_observation
from execution.dispatch import DispatchPlan, DispatchSession, dispatch_case
from execution.judge_channel import JudgementPlan, judge_channel_from_roster
from ingestion.cases import build_evaluation_cases
from ingestion.loaders import load_corpus

from tests.cases.consistency_support import measured_outcome
from tests.cases.observation_records import measured_fields, skip_fields
from tests.cases.step_recording import (
    record_observation_step,
    record_remaining_steps,
)

logger = logging.getLogger(__name__)

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
def shipped_corpus() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """Return every shipped task and rule set, loaded once.

    **Through the harness's `load_corpus`**, which chooses each file's reader
    from its suffix, so a CSV task file loads as readily as a YAML one. The
    corpus is the one `--golden-rules` names, falling back to this repository's
    own `data/`: the harness owns no corpus and cannot know what the default is
    (harness `tier1_ingestion.md` sections 4.5 and 4.6).

    **Tuples rather than lists, because the result is cached.** A caller that
    appended to a shared list would change what every later caller sees, and the
    callers here are tests.

    Returns:
        tuple: Every task, then every rule set.
    """
    named, policy = corpus_selection()
    root = named or (repository_root() / "data")
    tasks, rules = load_corpus(
        root, **({"unknown_columns": policy} if policy else {})
    )
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


def task_material(task: Any, candidate_output: str) -> UnauthoredMaterial:
    """Return the material a response is evaluated against: the answer and every instruction.

    The system instruction, the prompt and the documents travel with the
    answer, so the judge is given everything the candidate was given
    (``docs/design/consumer_ci.md`` section 6.4.3).

    Args:
        task (Any): The task the response answered.
        candidate_output (str): The response text.

    Returns:
        UnauthoredMaterial: What the pipeline screens and isolates.
    """
    return UnauthoredMaterial(
        candidate_output=candidate_output,
        system_instruction=task.system_instruction,
        task_instruction=task.user_prompt,
        context_documents={
            document.document_id: document.content
            for document in task.context_documents
        },
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
            report a harness error**, which reads as an instrument defect
            rather than a
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
    # THE PRIMARY CARRY GUARD, POPULATED HERE. Harness
    # `cmn_verdict_and_cli.md` section 7.6.2.
    record_rule_set_hash(config, shipped_corpus()[1])

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
    """Return the run's one session, built on first use.

    Delegates to a cached builder keyed on the engine and the ceiling, which
    are what define a session. **One session per run is the whole point**: it
    holds the spend accumulated toward ``--max-spend``, the time the roster's
    spacing is measured from, and the consecutive failures that open the
    circuit breaker, and a session rebuilt per observation discards all three.

    Design: ``consumer_ci.md`` section 4.15.

    Args:
        config (Any): pytest's configuration.

    Returns:
        DispatchSession: The run's session.
    """
    return _session(
        str(config.getoption("--engine") or ""),
        float(config.getoption("--max-spend") or 0.0),
    )


def run_session(engine: str, ceiling: float) -> DispatchSession:
    """Return the run's session for an engine and ceiling, the one ``dispatch_session`` returns.

    Args:
        engine (str): The candidate engine, ``--engine``.
        ceiling (float): ``--max-spend``, zero for none.

    Returns:
        DispatchSession: The cached session.
    """
    return _session(engine, ceiling)


@lru_cache(maxsize=4)
def _session(engine: str, ceiling: float) -> DispatchSession:
    """Build one session for an engine and ceiling, from the roster and flags.

    **Spacing is per engine because free-tier ceilings differ.** A session built
    without it would issue every request at once and be rate limited into a run
    that measures the limiter rather than the model.

    **The ceiling arrives here or nowhere.** `--max-spend` was declared as an
    option, the session carried the field, and the refusal was written and
    tested, while this function read only the spacing: the ceiling was
    unreachable from a command line. A cap nobody can set is not a cap.

    **The price table comes with it**, because a ceiling without rates cannot be
    computed, and an uncomputable ceiling stops a budgeted run rather than
    pretending to hold (harness `MQC_EXE_UNI_113702`).

    Args:
        config (Any): pytest's configuration.

    Returns:
        DispatchSession: Pacing, circuit-breaker and spending state. **The table
        is loaded only where a ceiling is set**, so a replay gate neither reads
        the file nor prices anything it did not pay for.
    """
    roster = engine_roster()
    spacing = roster[engine].spacing_sec if engine in roster else 0.0

    if ceiling <= 0:
        return DispatchSession(spacing_sec=spacing)

    return DispatchSession(
        spacing_sec=spacing,
        max_spend=ceiling,
        prices=load_price_table(packaged_config_root() / "pricing.yaml"),
        # THE RUN'S OWN DATE, read once here rather than per response. A run
        # spanning midnight prices every request the same way, which is what
        # makes two readings of one corpus agree.
        priced_on=project_today(),
    )



def judgement_plan(config: Any, candidate_engine: str) -> JudgementPlan:
    """Return how this invocation obtains judgements.

    **`--judge-mode` defaults to `--mode`** and the incoherent quadrant is
    refused at parsing, which `resolve_judge_mode` already does (harness
    ``tier3_evaluation.md`` section 5A.5).

    **This is the difference between a free pull request and a quota bill.**
    `FixtureKey` keys the candidate only, so without this plan a bound judge
    would be a live call whatever `--mode` says, and a replay run that judged
    would spend provider quota on every pull request.

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
    run: tuple[str, float] = ("", 0.0),
) -> Any:
    """Return one judge channel, built once per distinct configuration.

    **Cached because pacing is per channel.** A fresh channel per case would
    reset `last_request_at` and defeat the spacing the free tier requires,
    which is the same reason `dispatch_session` is cached. **That claim was
    false when written**: the session was rebuilt per observation until
    2026-10-02, so this docstring asserted a property the code lacked
    (`consumer_ci.md` section 4.15).

    Args:
        engine (str): The judge engine, empty for the configured primary.
        mode (str): The resolved judge mode.
        record (bool): Whether to store what is obtained.
        keep (bool): Whether to hold the connection between judgements.
        fill (bool): Whether to replay a judgement already recorded rather
            than asking again. **Part of the cache key**, because two
            channels differing only in this are different configurations.
        run (tuple[str, float]): The candidate engine and ``--max-spend``,
            zero for no ceiling. The candidate is which engine produced what
            is graded, **part of the cache key for the same reason**, and the
            reason is sharper here: a channel cached under one candidate and
            handed to a run grading another would address the first engine's
            judgement files, which is the collision section 7.9.3 of the
            harness design records. The pair keys the run's session, which
            the plan carries as its budget so every judge call counts against
            the ceiling (``consumer_ci.md`` section 7.4.3).

    Returns:
        Any: The :class:`JudgeChannel`.
    """
    candidate, ceiling = run
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
            budget=_session(candidate, ceiling),
        ),
    )


def judge_binding(config: Any, candidate_engine: str) -> Any:
    """Return the judge that decides, which is the only judge there is.

    **One judge, by scope.** A3.2 records why: divergence between judges is a
    finding about judges, and acting on it needs a judge over the judges, which
    does not bottom out. What checks this one is calibration against authored
    samples, whose mistakes are stated and therefore known.

    Args:
        config (Any): pytest's configuration.
        candidate_engine (str): Which engine produced the response, recorded so
            that self-preference is a comparison rather than a guess.

    Returns:
        Any: The :class:`JudgeBinding`.
    """
    # THE JUDGE WITHHELD ON REQUEST, `--judge-mode off`, in a debug run that
    # checks the screen and the assertions alone. Decided before a plan is
    # built, since a plan names live or replay; no channel is built, so no
    # judge is reached (harness `tier3_evaluation.md` section 5A.5.3).
    requested = resolve_judge_mode(
        config.getoption("--mode"), config.getoption("--judge-mode") or ""
    )
    if requested == _JUDGE_OFF:
        return JudgeBinding(candidate_engine=candidate_engine, withheld=True)
    plan = judgement_plan(config, candidate_engine)
    # THE NAMED JUDGE, NOT A HARDCODED EMPTY STRING. This passed "" and the
    # roster's judge graded every run, while the flag is recorded, so a run
    # naming a judge produced metadata attributing its scores to an engine that
    # did not produce them. Empty still means "take the configured one", which
    # is why the dropped argument read as a deliberate choice.
    # Design `consumer_ci.md` section 4.13.
    channel = _channel(
        str(config.getoption("--judge-engine") or ""),
        plan.mode,
        plan.record,
        bool(config.getoption("--keep-connection")),
        plan.fill_gaps,
        (candidate_engine, float(config.getoption("--max-spend") or 0.0)),
    )
    return JudgeBinding(
        invoke=channel.invoke,
        judge_engine=channel.engine,
        candidate_engine=candidate_engine,
    )


def judge_stopped(config: Any, candidate_engine: str) -> Optional[str]:
    """Return the code this run's judge stopped answering on, or None.

    None as well where the run withholds the judge, since nothing is asked.
    Design: ``consumer_ci.md`` section 6.4.5, harness ``tier2_execution.md``
    section 8.3.3.

    Args:
        config (Any): pytest's configuration.
        candidate_engine (str): Which engine produced what is graded.

    Returns:
        Optional[str]: The harness code the judge channel stopped on.
    """
    requested = resolve_judge_mode(
        config.getoption("--mode"), config.getoption("--judge-mode") or ""
    )
    if requested == _JUDGE_OFF:
        return None
    plan = judgement_plan(config, candidate_engine)
    channel = _channel(
        str(config.getoption("--judge-engine") or ""),
        plan.mode,
        plan.record,
        bool(config.getoption("--keep-connection")),
        plan.fill_gaps,
        (candidate_engine, float(config.getoption("--max-spend") or 0.0)),
    )
    return getattr(channel, "stopped", None)


def judging_requested(config: Any) -> bool:
    """Return whether the run asked for a judgement on a case whose assertions failed.

    The pipeline judges such a case by default while this corpus is in
    development, so what this answers is the narrower question the result
    records: whether the judgement was asked for by the invocation or inherited
    from that default.

    It never overrides a screen abort or a fatal failure, which withhold the
    judge whatever a run asks for.

    Design: ``consumer_ci.md`` sections 6.3 and 6.3.2.

    Args:
        config (Any): pytest's configuration.

    Returns:
        bool: True where ``--judge-on-failure`` was supplied.
    """
    return bool(config.getoption("--judge-on-failure"))


# THE JUDGE MODE THAT WITHHOLDS THE JUDGE (harness `tier3_evaluation.md`
# section 5A.5.3).
_JUDGE_OFF: Final[str] = "off"


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

    # QUARANTINE SAVES THE RUN'S COST, which is what it is for: a case already
    # known to fail buys nothing by being asked again. Skipped before the
    # request is formed, so no quota is spent, and the blocking band counts the
    # skip against the band it was selected into rather than excusing it.
    # Harness `cmn_verdict_and_cli.md` section 4.6.12.
    if case.case_id in quarantined_cases(config):
        # RECORDED BEFORE THE SKIP, carrying `quarantined` as its reason, so the
        # pass rate counts the failure quarantine declined to pay to measure
        # again. Released only by a recorded dispensation, harness design
        # section 4.6.13.
        record_observation(
            assemble_observation(
                skip_fields(
                    case,
                    None,
                    observation_index,
                    reason="quarantined",
                    code="QC_HARNESS_QUARANTINED",
                ),
                {},
            ),
            None,
        )
        pytest.skip(
            f"QC_HARNESS_QUARANTINED: {case.case_id} is quarantined, so it was "
            f"not dispatched"
        )

    # A JUDGE THAT STOPPED ANSWERING SKIPS A JUDGED CASE BEFORE ITS DISPATCH,
    # so a live run buys no response nobody can score (section 6.4.5). Asked
    # only for a rule carrying a rubric, the deterministic families binding no
    # judge.
    stopped = (
        judge_stopped(config, config.getoption("--engine"))
        if judge is None and case.golden_rules.rubric is not None else None
    )
    if stopped:
        record_observation(
            assemble_observation(
                skip_fields(case, None, observation_index, reason="environmental",
                            code=stopped),
                {},
            ),
            None,
        )
        pytest.skip(
            f"{stopped}: the judge stopped answering earlier in this run, so "
            f"{case.case_id} was not dispatched"
        )

    # LOGGED ON ENTRY, because the ledger below is computed from a result and a
    # crash between the request and the response leaves none. A timeout, an
    # adapter raising, a connection dropping: each would otherwise record
    # nothing about where the run had reached. `harness_test_taxonomy.md` section 8.
    marker = f"{case.case_id} observation {observation_index}"
    with entering(marker, 1, "ACTION", f"engine {config.getoption('--engine')}"):
        plan = dispatch_plan(config)
        session = dispatch_session(config)
    with entering(marker, 2, "ACTION", f"mode {plan.mode}"):
        outcome = dispatch_case(
            case,
            config.getoption("--engine"),
            plan,
            session,
            observation_index=observation_index,
        )

    # A HARNESS EVENT IS A SKIP, NEVER A FAILURE. `framework-rules.md`
    # section 4: a QC_HARNESS_* code says our infrastructure did not produce a
    # measurement, and recording that as a red case would assert something
    # about a model that was never asked. A missing fixture is the common one
    # before a corpus has been recorded.
    if outcome.taxonomy_code and outcome.taxonomy_code.startswith("QC_HARNESS_"):
        # RECORDED BEFORE THE SKIP, because a case that stopped at dispatch is
        # exactly the one whose later steps nobody can see.
        record_observation_step(case.case_id, observation_index + 1, outcome, None)
        # AND THE OBSERVATION, carrying `environmental`: our infrastructure did
        # not produce a measurement, which is not the model's failure and leaves
        # the pass rate (harness `harness_test_taxonomy.md` section 7.4.1).
        record_observation(
            assemble_observation(
                skip_fields(
                    case,
                    outcome,
                    observation_index,
                    reason="environmental",
                    code=outcome.taxonomy_code,
                ),
                {},
            ),
            outcome,
        )
        pytest.skip(
            f"{outcome.taxonomy_code}: {case.case_id} produced no measurement"
        )

    task = case.task
    context = ObservationContext(
        case_id=case.case_id,
        rules=case.golden_rules,
        material=task_material(task, outcome.response.text if outcome.response else ""),
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

    # THE FLAG REACHES THE PIPELINE HERE, and until 2026-11-02 nothing carried
    # it: it was declared, documented and recorded in the result metadata, and
    # no caller read it, so an authoring run that named it got the default.
    # This is the one production call site, so this line is the whole of the
    # wiring, and `115802` holds it (harness `tier3_evaluation.md` section
    # 4.2.0, design section 6.3.2).
    with entering(marker, 4, "ACTION", "screen, assertions and judge"):
        result = evaluate_observation(
            context, judge, judge_on_failure=judging_requested(config),
        )

    # THIS OBSERVATION'S STEP, per harness `harness_test_taxonomy.md` section
    # 8.2.2: one dispatch, its action and one verification, the pipeline
    # phases beneath. The harness computes it and this records it.
    record_observation_step(case.case_id, observation_index + 1, outcome, result)

    # RECORDED FOR THE REPORTING HOOK, which is the only place that knows the
    # case's verdict and so whether to attach the reproduction. Every
    # observation is recorded, passing or failing: the passing ones of a
    # failing case are exactly what a provider ticket needs. Harness design
    # cmn_verdict_and_cli.md sections 5.3 and 5.4.1.
    record_observation(
        assemble_observation(measured_fields(case, outcome, result, observation_index), {}),
        outcome,
        result,
    )
    return result


@lru_cache(maxsize=8)
def _quarantine_for(engine: str) -> frozenset[str]:
    """Return the case identifiers quarantined for one engine.

    **Cached, because every observation asks.** The file does not change
    within a run, and reading it per observation would read it hundreds of
    times.

    Args:
        engine (str): Which engine this run measures.

    Returns:
        frozenset[str]: The identifiers, empty where nothing is quarantined.
    """
    if not engine:
        return frozenset()
    entries = load_quarantine_for(repository_root() / "config", engine)
    return frozenset(str(entry.case_id) for entry in entries)


def quarantined_cases(config: Any) -> frozenset[str]:
    """Return what this invocation treats as quarantined.

    Args:
        config (Any): pytest's configuration, for the engine.

    Returns:
        frozenset[str]: The quarantined case identifiers.
    """
    return _quarantine_for(str(config.getoption("--engine") or ""))


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

    **And any failure earns two more.** Three runs to pass, five once one has
    failed, because a figure filed with a vendor rests on its denominator and
    thirds are not a rate a reader can weigh. The rule is the harness's
    (`cmn.observations.further_observations`) and this loop only dispatches
    what it asks for, per design section 4.9.2.2.

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
    configured = observation_count(config)
    results = [
        observe(config, task_id, rule_id, observation_index=index, judge=judge)
        for index in range(configured)
    ]

    # ESCALATION IS THE HARNESS'S RULE AND THIS LOOP DECIDES NOTHING, which is
    # the boundary in CLAUDE.md: the cases own no harness code. Design section
    # 4.9.2.2.
    # AN UNJUDGED OBSERVATION IS NO OUTCOME, and earns nothing (section 6.4.5).
    extra = further_observations([measured_outcome(entry) for entry in results])
    taken = len(results)
    results += [
        observe(config, task_id, rule_id, observation_index=taken + offset, judge=judge)
        for offset in range(extra)
    ]

    # THE ESCALATION STEPS NOT TAKEN AND THE COMPARISON, consumer_ci.md
    # section 9.4.3.3. Recorded only; the case is still decided by
    # `assert_consistent_pass`.
    record_remaining_steps(
        case_for(task_id, rule_id).case_id, results, configured=configured
    )
    return results
