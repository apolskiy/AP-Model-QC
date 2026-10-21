# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""What each recorded observation holds, and how its checks and judgement came out.

Created: 2026-10-16
Last updated: 2026-10-21

This file reads the replay fixtures for one engine, task and rule.
``recorded_request`` returns the request as sent, ``recorded_responses`` and
``recorded_observations`` every response with its text and tool calls,
``recorded_judgements`` the stored judge replies and ``judge_prompts`` what each
judge received. ``observation_outcomes`` replays the harness screen, the rule's
assertions and its tool expectation against each observation.

``tools.ticket_report`` calls these while building a finding's section and
renders what they return as the ticket's request, responses and per-observation
labels. Nothing is sent to a model, so a ticket shows exactly what the run saw.

Specified by ``docs/design/consumer_ci.md`` sections 9.5 and 9.5.5.4.
"""

import json
from pathlib import Path
from typing import Any, Final, Optional

from evaluation.assertions import run_assertions
from evaluation.judge import JudgeBinding
from evaluation.pipeline import (
    ObservationContext, evaluate_observation, observation_judge_request,
)
from evaluation.tool_compliance import evaluate_tool_compliance
from execution.normalize import ToolCall
from tests.cases.graded_support import case_for, task_material

# THE NAME A SCREEN STOP IS REPORTED UNDER, read by `tools.ticket_reasons`.
_SCREEN_CHECK: Final[str] = "A_HARNESS_SCREEN"


def observation_outcomes(
    task_id: str, rule_id: str, recordings: list[dict[str, Any]]
) -> list[tuple[int, bool, str]]:
    """Return each observation's outcome, by replaying the screen, its assertions and tool checks.

    **The harness screen decides first**, as it does in the run: an observation
    it stopped fails as ``A_HARNESS_SCREEN`` and its checks are not read
    (``consumer_ci.md`` section 9.5.5.7).

    **The checks are re-run rather than read from a report.** They are pure
    functions of the recorded text and calls, so this is deterministic, needs
    no credential and costs nothing, and it lets the document say which
    observation carried the problem instead of showing five and leaving the
    reader to find it.

    **The tool expectation is re-run too**, against the recorded calls and the
    task's offered tools, so a rule decided by a call reports the observation
    that made it (``consumer_ci.md`` section 9.5.5.4).

    **The rubric is not re-run.** It needs a judge, so an observation that
    passed every check is reported as such and nothing is claimed about its
    score.

    Args:
        task_id (str): The task identifier.
        rule_id (str): The rule set identifier.
        recordings (list): Each recorded observation's response, as stored.

    Returns:
        list: One entry per observation, as index, whether every check passed,
        and what failed when one did.
    """
    try:
        case = case_for(task_id, rule_id)
    except (KeyError, ValueError):
        return []
    offered = tuple(getattr(case.task, "available_tools", ()) or ())
    outcomes = []
    for index, response in enumerate(recordings):
        calls = tuple(
            ToolCall(tool_name=str(call.get("tool_name", "")),
                     arguments=dict(call.get("arguments") or {}),
                     sequence=int(call.get("sequence", position)))
            for position, call in enumerate(response.get("tool_calls") or ())
            if isinstance(call, dict)
        )
        text = str(response.get("text") or "")
        stopped = _screen_stop(case, index, text)
        if stopped:
            outcomes.append((index, False, stopped))
            continue
        results = run_assertions(
            case.golden_rules.assertions, text
        ) + evaluate_tool_compliance(
            calls, getattr(case.golden_rules, "tool_expectation", None), offered
        )
        failures = [
            f"{result.assertion_id} ({result.taxonomy_code}): {result.detail}"
            for result in results
            if not result.passed
        ]
        outcomes.append((index, not failures, "; ".join(failures)))
    return outcomes


def _screen_stop(case: Any, index: int, text: str) -> str:
    """Return what the harness screen stopped an observation on, or nothing.

    **The run's own decision**, from the harness evaluation with no judge
    bound, so the exemption for a rejected report is the one the run applied
    (``consumer_ci.md`` section 9.5.5.7).

    Args:
        case (Any): The evaluation case.
        index (int): The observation's index.
        text (str): The recorded response.

    Returns:
        str: The failure as ``A_HARNESS_SCREEN (QC_SEC_INJECTION_ATTEMPT): ...``
        naming each vector and what it matched, or empty when the screen let it
        through.
    """
    screen = evaluate_observation(_context(case, index, text), JudgeBinding()).screen
    if not screen.aborts:
        return ""
    matched = ", ".join(
        f"{finding.vector} matched '{finding.excerpt}'".replace(";", ",")
        for finding in screen.findings
    )
    return f"{_SCREEN_CHECK} ({screen.taxonomy_code}): {matched}"


def _context(case: Any, index: int, text: str) -> ObservationContext:
    """Return one recorded observation as the run evaluated it.

    Args:
        case (Any): The evaluation case.
        index (int): The observation's index.
        text (str): The recorded response.

    Returns:
        ObservationContext: The context the pipeline is given.
    """
    return ObservationContext(
        case_id=case.case_id,
        rules=case.golden_rules,
        material=task_material(case.task, text),
        declared_adversarial=case.task.contains_adversarial_content,
        observation_index=index,
    )


def judge_prompts(
    task_id: str, rule_id: str, recordings: list[dict[str, Any]],
    judgements: list[Optional[dict[str, Any]]],
) -> list[str]:
    """Return the prompt each judged observation's judge received, empty where none was.

    The prompt its recording stored, or the one the harness composes from the
    recorded response for a recording made before recordings stored one
    (``consumer_ci.md`` section 9.5.5.8).

    Args:
        task_id (str): The task identifier.
        rule_id (str): The rule set identifier.
        recordings (list): Each recorded observation's response, as stored.
        judgements (list): Each observation's recorded judgement, None where
            the judge never saw it.

    Returns:
        list[str]: One prompt per observation, in order.
    """
    try:
        case = case_for(task_id, rule_id)
    except (KeyError, ValueError):
        case = None
    prompts: list[str] = []
    for index, response in enumerate(recordings):
        judgement = judgements[index] if index < len(judgements) else None
        if judgement is None:
            prompts.append("")
        elif judgement.get("prompt"):
            prompts.append(str(judgement["prompt"]))
        elif case is not None and case.golden_rules.rubric is not None:
            prompts.append(observation_judge_request(
                _context(case, index, str(response.get("text") or ""))
            ).rendered())
        else:
            prompts.append("")
    return prompts


def recorded_responses(
    root: Path, engine: str, task: str, rule: str
) -> list[dict[str, Any]]:
    """Return every recorded response for one pair, as stored, in observation order.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose recordings to read.
        task (str): The task identifier.
        rule (str): The rule set identifier.

    Returns:
        list[dict]: Each observation's response. Empty when the pair was never
        recorded for this engine; an unreadable recording reads as text saying
        so, with no call.
    """
    folder = root / "tests" / "fixtures" / "replay" / engine / task / rule
    if not folder.is_dir():
        return []
    responses: list[dict[str, Any]] = []
    for source in sorted(folder.glob("*.json"), key=lambda path: int(path.stem)):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            responses.append({"text": "[unreadable recording]"})
            continue
        responses.append(dict(payload.get("response") or {}))
    return responses


def recorded_observations(root: Path, engine: str, task: str, rule: str) -> list[str]:
    """Return what each recorded observation shows a reader, in observation order.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose recordings to read.
        task (str): The task identifier.
        rule (str): The rule set identifier.

    Returns:
        list[str]: Each observation's text followed by one line per tool call,
        naming the tool and its arguments (``consumer_ci.md`` section 9.5.5.4).
        Empty when the pair was never recorded for this engine, which is
        reported rather than treated as an empty answer.
    """
    shown: list[str] = []
    for response in recorded_responses(root, engine, task, rule):
        lines = [str(response["text"])] if response.get("text") else []
        lines.extend(
            f"Tool call: {call.get('tool_name', '?')}"
            f"({json.dumps(call.get('arguments') or {}, sort_keys=True)})"
            for call in response.get("tool_calls") or ()
            if isinstance(call, dict)
        )
        shown.append("\n".join(lines))
    return shown


def recorded_request(
    root: Path, engine: str, task: str, rule: str
) -> Optional[dict[str, Any]]:
    """Return the request a recording stored, or None where it stored none.

    **Observation 0 is enough.** The fixture key is the pair and the
    observation index, and the request is identical across a pair's
    observations by construction: the hash is computed from it and locates
    every one of them.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose recording to read.
        task (str): The task identifier.
        rule (str): The rule set identifier.

    Returns:
        Optional[dict]: The composed request as sent, or None where the pair
        was never recorded or the recording predates the field
        (``tier2_execution.md`` section 7.13).
    """
    folder = root / "tests" / "fixtures" / "replay" / engine / task / rule
    if not folder.is_dir():
        return None
    for source in sorted(folder.glob("*.json"), key=lambda path: path.name):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        stored = payload.get("request")
        if isinstance(stored, dict):
            return stored
    return None


def recorded_judgements(
    root: Path, engine: str, task: str, rule: str, count: int
) -> list[Optional[dict[str, Any]]]:
    """Return each observation's recorded judgement, None where there is none.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose responses were judged.
        task (str): The task identifier.
        rule (str): The rule set identifier.
        count (int): How many observations the pair recorded.

    Returns:
        list: One entry per observation, in order. The judge's folder is
        whichever one holds this pair; None where no judgement was recorded,
        which is the case for every observation a check stopped.
    """
    folder = root / "tests" / "fixtures" / "replay" / "judgements" / engine
    found: list[Optional[dict[str, Any]]] = [None] * count
    if not folder.is_dir():
        return found
    for judge in sorted(path for path in folder.iterdir() if path.is_dir()):
        pair = judge / task / rule
        for index in range(count):
            source = pair / f"{index}.json"
            if found[index] is None and source.is_file():
                try:
                    found[index] = json.loads(source.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
    return found
