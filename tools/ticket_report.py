# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The ticket report, which writes each engine's filed findings as pages ready to submit.

Created: 2026-10-05
Last updated: 2026-10-28

This file contains ``page_for``, which builds one engine's findings page,
``finding_section``, which writes one finding's defect report with its problem,
the request as sent, every recorded response, the expected rule and a replay
command, and ``main``, which writes a page per engine and one ticket file per
filed finding under ``reports/tickets/``.

It is run by hand, normally after ``tools.findings`` has updated a register.
Its sections are assembled from ``tools.ticket_recordings``,
``tools.ticket_reasons`` and ``tools.ticket_framing``, and ``tools.ticket_files``
writes the files. A person submits each ticket to its vendor, and
``tools.finding_evidence`` reads the page when a finding is reviewed.

Specified by ``docs/design/consumer_ci.md`` section 9.5.

**Three sources had to be joined by hand before this existed.** The findings
register carries the claim, the corpus carries the prompt, and the replay
fixtures carry what the model said; nothing carried all three, so filing a
ticket meant two lookups per finding and three more for an inconsistency.

| Source | Supplies |
|---|---|
| ``config/findings/<engine>.yaml`` | The claim, the taxonomy code, expected and actual |
| ``data/tasks/*.yaml`` | The constraints, and the fallback where a
  recording predates the stored request |
| ``tests/fixtures/replay/<engine>/`` | **The request as sent**, and every
  recorded observation's text |

**The request is recorded, not reconstructed**, since 2026-10-11
(``consumer_ci.md`` section 9.5.3). It used to come from the corpus, which shows
what the case *declares* rather than what the adapter *composed*: the system
instruction, the message roles, the ordering and the model identity are the same
only while the adapter is correct, and that is the thing a reader is checking.
**A recording that predates the field says so** rather than falling back to the
corpus and presenting it as the call.

**Every observation is shown, not just one.** An inconsistency finding is a
claim about variance, and a single transcript cannot carry it: three passes out
of five is the finding, and a reader needs all of them.

Usage::

    python -m tools.ticket_report                 # every rostered engine
    python -m tools.ticket_report --engine claude
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Final, Optional

import yaml

from evaluation.aggregation import CriterionScore, aggregate
from execution.adapters.registry import reproduction_curl, reproduction_snippet
from tests.cases.graded_support import case_for
from tests.cases.suite_support import case_rules_from_suite
from tools.register_files import to_file
from tools.ticket_recordings import (
    judge_prompts,
    observation_outcomes,
    recorded_judgements,
    recorded_observations,
    recorded_request,
    recorded_responses,
)
from tools.ticket_files import (
    GENERATED_MARK,
    drop_engine_output,
    filing_sheet,
    page_name,
    write_tickets,
)
from tools.ticket_framing import framed_problem
from tools.ticket_reasons import failure_reasons, rule_lines

_DEFAULT_OUT: Final[Path] = Path("reports") / "tickets"
_ENGINES: Final[tuple[str, ...]] = ("gemini", "openai", "claude", "grok")
_BACKTICKS: Final[re.Pattern[str]] = re.compile("`+")


# WHAT EACH CODE MEANS TO SOMEONE WHO DOES NOT WORK HERE. The register's
# `actual` field is generated from the assertion that fired and reads like
# instrumentation: "A_GND_STATES_SOURCED_FIGURE (QC_LLM_SOURCE_ALTERATION):
# required substring absent". That belongs under Diagnosis. **The problem
# statement is what the reader is being asked to accept**, so it is written in
# the words they would use.
#
# THE VOCABULARY LIVES HERE, NOT IN THE HARNESS REGISTRY. The registry ranks
# codes by criticality, which every consumer needs; this phrasing is for one
# audience, a vendor reading a report, and `framework-rules.md` section 4.1
# forbids a second registry of the same fact rather than a different one.
_PROBLEM: Final[dict[str, str]] = {
    "QC_LLM_SOURCE_ALTERATION":
        "The model stated a figure the source does not support",
    "QC_LLM_INJECTION_SUSCEPTIBLE":
        "The model followed an instruction planted in the content it was "
        "asked to process",
    "QC_LLM_GOAL_HIJACK":
        "The model abandoned the task it was given for one planted in the "
        "content it was asked to process",
    "QC_LLM_INSTRUCTION_DRIFT":
        "The model did not follow an instruction it was given",
    "QC_LLM_MATCH_MISCOMPUTED":
        "The model reported a match the supplied requirements do not give",
    "QC_LLM_LENGTH_VIOLATION":
        "The model exceeded a length the prompt set",
    "QC_LLM_RUBRIC_FAILURE":
        "The model's answer scored below the threshold the rubric sets",
    "QC_LLM_DEFECT_MISSED":
        "The model did not report a defect present in the material it was "
        "given",
    "QC_LLM_HALLUCINATION":
        "The model stated something the material does not support",
    "QC_LLM_CONTEXT_OMISSION":
        "The model answered without using the context it was supplied",
    "QC_LLM_AMBIGUITY_UNHANDLED":
        "The model resolved an ambiguity instead of raising it",
    "QC_LLM_UNSOURCED_CLAIM":
        "The model asserted a figure no supplied source states",
    "QC_LLM_INCONSISTENT":
        "The model answered the same request differently on different "
        "attempts",
    # A BARE CODE IS NOT A PROBLEM STATEMENT (section 9.5.5.6). Both of these
    # opened fifteen tickets on 2026-10-20 as the code and the register's
    # instrumentation text.
    "QC_SEC_INJECTION_ATTEMPT":
        "The model's answer carried an instruction planted in the content it "
        "was asked to process",
    "QC_LLM_TOOL_VIOLATION":
        "The model called a tool it was told never to use",
}


def load_tasks(root: Path) -> dict[str, dict[str, Any]]:
    """Return every shipped task by identifier.

    Args:
        root (Path): The repository root.

    Returns:
        dict[str, dict]: Task identifier to its definition.
    """
    tasks: dict[str, dict[str, Any]] = {}
    for source in sorted((root / "data" / "tasks").glob("*.yaml")):
        payload = yaml.safe_load(source.read_text(encoding="utf-8")) or []
        entries = payload if isinstance(payload, list) else payload.get("tasks", [])
        for entry in entries:
            if isinstance(entry, dict) and entry.get("task_id"):
                tasks[str(entry["task_id"])] = entry
    return tasks


def judged_outcome(
    judgement: Optional[dict[str, Any]], rubric: Any
) -> Optional[tuple[bool, float, str]]:
    """Return whether a recorded judgement clears its rubric, and why.

    Args:
        judgement (Optional[dict]): The recorded judgement, or None.
        rubric (Any): The rule's rubric, whose strategy and threshold decide.

    Returns:
        Optional[tuple]: Whether it passed, the aggregated score, and each
        criterion's score with the judge's rationale. None where there is no
        judgement or no rubric to read it against.
    """
    if judgement is None or rubric is None:
        return None
    scores = (judgement.get("reply") or {}).get("scores") or {}
    weights = {criterion.criterion_id: criterion.weight for criterion in rubric.criteria}
    result = aggregate(
        rubric.aggregation,
        [CriterionScore(criterion_id=name, score=float(detail.get("score", 0)),
                        weight=weights.get(name, 1.0))
         for name, detail in scores.items()],
        threshold=rubric.threshold,
        parameters=dict(rubric.aggregation_params or {}),
    )
    if result.value is None:
        return None
    reasons = "; ".join(
        f"`{name}` scored {detail.get('score')}: {detail.get('rationale', '')}"
        for name, detail in scores.items()
    )
    return bool(result.passed), float(result.value), reasons


def heading(case: str) -> str:
    """Return a finding's heading: the case name with its number in brackets.

    Args:
        case (str): The full case name.

    Returns:
        str: The Markdown heading.
    """
    parts = case.split("_")
    number = parts[3] if len(parts) > 3 else ""
    return f"## `{case}` ({number})"


def reproduce_command(engine: str, case: str) -> str:
    """Return the replay command that re-runs one case from its recordings.

    Args:
        engine (str): The engine whose recordings to replay.
        case (str): The full case name.

    Returns:
        str: The command. ``--with-prerequisites`` is always present, because a
        case resting on a foundation is refused without it.
    """
    parts = case.split("_")
    number = parts[3] if len(parts) > 3 else case
    return (
        f"pytest --engine {engine} --mode replay --tests {number} "
        f"--with-prerequisites"
    )


def expected_block(task_id: str, rule_id: str, task: Optional[dict[str, Any]]) -> str:
    """Return what a correct response is, for the Expected part of a ticket.

    Args:
        task_id (str): The task identifier.
        rule_id (str): The rule set identifier.
        task (Optional[dict]): The task definition, for its constraint texts.

    Returns:
        str: Markdown opening with **the rule** (section 9.5.5.6): the
        constraints the case references, the standing rule a check kind
        enforces, the tools it requires or forbids, and a judged criterion's
        threshold. Then each rubric criterion with what it asks and its top
        exemplar, which is a correct response by construction.
    """
    try:
        rules = case_for(task_id, rule_id).golden_rules
    except (KeyError, ValueError):
        return "_The rule could not be resolved, so no expected response is shown._"
    stated = rule_lines(rules, task) or ["_The rule states no constraint text._"]
    lines: list[str] = ["**The rule**", "", *stated, ""]
    rubric = getattr(rules, "rubric", None)
    for criterion in getattr(rubric, "criteria", []):
        top = criterion.anchors.get(max(criterion.anchors)) if criterion.anchors else None
        lines.append(f"*{criterion.name}*: {_sentence(criterion.description)}")
        if top is not None and top.exemplar:
            lines.extend(["", "A response that meets it:", "", *fenced(top.exemplar)])
        lines.append("")
    return "\n".join(lines).rstrip()


def _message_texts(request: dict[str, Any]) -> list[tuple[str, str]]:
    """Return the role and text of each message in a composed request.

    **Provider-agnostic, because the shape differs per adapter.** One sends
    ``messages`` with ``role`` and ``content``, another sends ``contents`` with
    ``parts``, and a system instruction may be a top-level field or a message.

    Args:
        request (dict): The composed request.

    Returns:
        list[tuple]: Each role paired with its text, in the order sent.
    """
    found: list[tuple[str, str]] = []
    # AND INSIDE `config`, WHICH IS WHERE ONE PROVIDER PUTS IT. Gemini carries
    # the system instruction in the request config rather than as a message,
    # so every ticket against it showed the documents and omitted the
    # instruction that defines the task: an incomplete reproduction, and the
    # first thing a vendor engineer would reject (section 9.5.3).
    config = request.get("config") if isinstance(request.get("config"), dict) else {}
    system = (
        request.get("system")
        or request.get("system_instruction")
        or config.get("system_instruction")
    )
    if isinstance(system, str) and system.strip():
        found.append(("system", system))
    for key in ("messages", "contents"):
        entries = request.get(key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            role = str(entry.get("role") or key)
            content = entry.get("content", entry.get("parts", ""))
            if isinstance(content, str):
                found.append((role, content))
            elif isinstance(content, list):
                joined = "\n".join(
                    str(piece.get("text", piece)) if isinstance(piece, dict)
                    else str(piece)
                    for piece in content
                )
                found.append((role, joined))
    return found


def _request_block(task: Optional[dict[str, Any]]) -> str:
    """Return the request as a ticket shows it.

    Args:
        task (Optional[dict]): The task definition, or None when unmapped.

    Returns:
        str: Markdown for the prompt, constraints and context.
    """
    if task is None:
        return (
            "_The case could not be mapped to a shipped task, so the request "
            "is not reconstructible here._\n"
        )
    lines = ["**Prompt**\n", *fenced(str(task.get("user_prompt", ""))), ""]

    constraints = task.get("constraints") or []
    if constraints:
        lines.append("**Stated constraints**\n")
        for entry in constraints:
            if isinstance(entry, dict):
                lines.append(
                    f"- `{entry.get('constraint_id', '')}` "
                    f"({entry.get('kind', '')}): {entry.get('text', '')}"
                )
        lines.append("")

    documents = task.get("context_documents") or []
    if documents:
        lines.append("**Context supplied with the request**\n")
        for entry in documents:
            if not isinstance(entry, dict):
                continue
            lines.append(f"*{entry.get('title', entry.get('document_id', ''))}*\n")
            lines.extend([*fenced(str(entry.get("content", ""))), ""])
    return "\n".join(lines)


def _scenario(task: Optional[dict[str, Any]]) -> str:
    """Return the scenario in one sentence, from the task's own instruction.

    **The first line of a report has to say what was being attempted**, per
    section 9.5.1. A reader opening a ticket needs the situation before the
    detail, and the task's instruction is the situation.

    Args:
        task (Optional[dict]): The task definition, or None when unmapped.

    Returns:
        str: One sentence, or a statement that the task is not resolvable.
    """
    if task is None:
        return "a scenario this report could not resolve to a shipped task"
    instruction = " ".join(str(task.get("user_prompt", "")).split())
    if len(instruction) > 150:
        instruction = instruction[:147].rstrip() + "..."
    planted = any(
        "assistant" in str(document.get("content", "")).lower()
        or "instruction" in str(document.get("content", "")).lower()
        for document in task.get("context_documents") or []
    )
    carried = (
        " with an instruction planted in the supplied document"
        if planted else ""
    )
    return f'the model was asked: "{instruction}"{carried}'



def _diagnosis(entry: dict[str, Any]) -> str:
    """Return what the check found, or nothing when there is nothing to add.

    **A canary case has no diagnosis worth printing.** The response either
    carried the token or did not, and the problem statement already said so. A
    `claim` assertion has one worth reading: it quotes the sentence it read,
    which is what makes the finding checkable rather than assertable.

    Args:
        entry (dict): The register entry.

    Returns:
        str: The diagnosis, or an empty string.
    """
    actual = str(entry.get("actual") or "").strip()
    if not actual:
        return ""
    code = str(entry.get("taxonomy_code") or "")
    # THE PROBLEM STATEMENT ALREADY CARRIES A BARE CANARY RESULT, and repeating
    # it would be the old layout's defect in a new place.
    if actual == f"{code}: pattern found" or actual.endswith("required substring present"):
        return ""
    # "NO ASSERTION FAILED" ON A FAILING FINDING reads as the opposite of the
    # claim: the screen or the judge decided it, and Why it fails says which
    # (section 9.5.5.6).
    if actual.rstrip(".") == "no assertion failed":
        return ""
    return _sentence(actual)


def _input_block(
    task: Optional[dict[str, Any]],
    request: Optional[dict[str, Any]] = None,
) -> list[str]:
    """Return the request as sent, reading the recording where there is one.

    **The recording is preferred over the corpus** (``consumer_ci.md`` section
    9.5.3): the corpus shows what the case declares and the recording shows
    what the provider received, and a ticket must not ask a vendor to trust our
    composer.

    Args:
        task (Optional[dict]): The task definition, the fallback source.
        request (Optional[dict]): The composed request the recording stored.

    Returns:
        list[str]: Markdown lines. **The readable text and then the exact
        call**, because a reviewer reads the prompt and a vendor pastes the
        request, and those are two different needs.
    """
    if request is not None:
        out = ["**Input**", "", "_As recorded, the call the provider received._", ""]
        model = request.get("model")
        if model:
            out.extend([f"*Model requested:* `{model}`", ""])
        for role, body in _message_texts(request):
            out.extend([f"*{role.capitalize()}*", "", *fenced(str(body)), ""])
        return out

    if task is None:
        return ["**Input**", "", "_The task could not be resolved._", ""]

    out = [
        "**Input**", "",
        "_This recording predates the stored request, so the text below is the "
        "corpus the run dispatched rather than the call itself. Re-record to "
        "replace it (`tier2_execution.md` section 7.13.2)._", "",
    ]
    system = str(task.get("system_instruction") or "").strip()
    if system:
        out.extend(["*System instruction*", "", *fenced(system), ""])
    out.extend(["*Prompt*", "", *fenced(str(task.get("user_prompt", ""))), ""])
    documents = task.get("context_documents") or []
    for item in documents:
        if not isinstance(item, dict):
            continue
        out.extend([
            f"*Supplied: {item.get('title', item.get('document_id', ''))}*",
            "", *fenced(str(item.get("content", ""))), "",
        ])
    tools = [
        item for item in (task.get("available_tools") or []) if isinstance(item, dict)
    ]
    if tools:
        # THE OFFERED SET IS PART OF THE INPUT for a tool case, and omitting it
        # made a finding about inventing a tool unreadable: a reader could not
        # tell which names existed.
        offered = ", ".join(f"`{item.get('tool_name', '')}`" for item in tools)
        out.extend([f"*Tools offered:* {offered}", ""])
    return out


def _reproduce_block(
    engine: str, request: Optional[dict[str, Any]], case: str
) -> list[str]:
    """Return every way to re-issue the call, the exact ones first.

    Args:
        engine (str): The engine the call was made against.
        request (Optional[dict]): The composed request the recording stored.
        case (str): The full case name, for the replay command.

    Returns:
        list[str]: Markdown lines: a ``curl`` where the recording is the wire
        body, the SDK call with every recorded parameter, then the replay
        command, which needs no credential (``consumer_ci.md`` section 9.5.5).
    """
    out = ["**Reproduce**", ""]
    if request is not None:
        command = reproduction_curl(engine, request)
        if command:
            out.extend(["The recorded request, posted unchanged:", "",
                        *fenced(command, "bash"), ""])
        snippet = reproduction_snippet(engine, request)
        if snippet:
            out.extend(["The same call through the provider's SDK:", "",
                        *fenced(snippet, "python"), ""])
    out.extend([
        "From this repository, replaying the committed recordings, with no "
        "credential and no cost:", "",
        *fenced(reproduce_command(engine, case)), "",
    ])
    return out


def _output_block(
    engine: str,
    responses: list[str],
    outcomes: list[tuple[int, bool, str]],
    judged: Optional[list[Optional[tuple[bool, float, str]]]] = None,
    prompts: Optional[list[str]] = None,
) -> list[str]:
    """Return every observation, each labelled by its checks and its judgement.

    Args:
        engine (str): The engine under test.
        responses (list): Each recorded observation's text.
        outcomes (list): Per-observation assertion outcomes, possibly empty
            when the case could not be resolved.
        judged (Optional[list]): Per-observation judgement outcomes from
            :func:`judged_outcome`, None where the judge was not called.
        prompts (Optional[list]): Each observation's judge prompt, empty where
            the judge never saw it, shown collapsed beneath the response
            (``consumer_ci.md`` section 9.5.5.8).

    Returns:
        list[str]: Markdown lines. **Every observation is shown**, passing ones
        included, because an inconsistency is a claim about all of them
        (``consumer_ci.md`` section 9.5.5).
    """
    # EVERY RECORDING KEEPS ITS PLACE. Dropping an empty body shifted the
    # numbering against the per-observation verdicts (section 9.5.5.4).
    bodies = list(responses)
    if not any(body.strip() for body in bodies):
        return [
            "**Responses**", "",
            f"_No recording at `tests/fixtures/replay/{engine}/`, so this "
            f"finding cannot show what was returned._", "",
        ]
    verdicts = {index: (passed, detail) for index, passed, detail in outcomes}
    judgements = list(judged or [])
    labelled = [
        _label(verdicts.get(index, (True, "")),
               judgements[index] if index < len(judgements) else None)
        for index in range(len(bodies))
    ]
    failing = sum(1 for failed, _ in labelled if failed)
    out = [f"**Responses.** The problem appeared on {failing} of {len(bodies)} "
           f"observations, every one shown.", ""]
    shown = list(prompts or [])
    for index, body in enumerate(bodies):
        label = labelled[index][1]
        out.extend([f"*Observation {index + 1} of {len(bodies)}.* "
                    f"{label[:1].upper()}{label[1:]}", "",
                    *fenced(body or "[no text and no tool call]"), ""])
        if index < len(shown) and shown[index]:
            out.extend(["<details>",
                        f"<summary>Judge prompt, observation {index + 1} of {len(bodies)}"
                        f"</summary>", "", *fenced(shown[index]), "", "</details>", ""])
    return out


def fenced(text: str, info: str = "") -> list[str]:
    """Return text inside a code fence.

    Args:
        text (str): What the fence holds, shown as recorded.
        info (str): The fence's language tag, if any.

    Returns:
        list[str]: The opening fence, the text, and the closing fence. The fence
        is one backtick longer than the longest run inside the text and never
        shorter than three, so a response carrying its own fenced block stays
        inside this one (``consumer_ci.md`` section 9.5.5.1).
    """
    longest = max((len(run) for run in _BACKTICKS.findall(text)), default=0)
    fence = "`" * max(3, longest + 1)
    return [f"{fence}{info}", text.rstrip(), fence]


def _label(
    checks: tuple[bool, str], judgement: Optional[tuple[bool, float, str]]
) -> tuple[bool, str]:
    """Return whether one observation failed, and its label.

    Args:
        checks (tuple): Whether its checks passed, and what failed if not.
        judgement (Optional[tuple]): Its judged outcome, None when unjudged.

    Returns:
        tuple: Whether it failed, and the label naming its checks and judgement.
    """
    passed, detail = checks
    if not passed:
        return True, f"failed its checks, so the judge was not called (not judged): {detail}"
    if judgement is None:
        return False, "passed its checks"
    if not judgement[0]:
        return True, f"failed: the judge scored it {judgement[1]:g}. {judgement[2]}"
    return False, f"passed its checks and the judge, scoring {judgement[1]:g}. {judgement[2]}"


def finding_section(
    root: Path,
    engine: str,
    entry: dict[str, Any],
    pairs: dict[str, tuple[str, str]],
    tasks: dict[str, dict[str, Any]],
) -> list[str]:
    """Return the defect report for one finding.

    **Case, problem, diagnosis, input, output**, per section 9.5.2. The shape
    is the one the project owner set for the feedback this repository files
    about its own tooling, and it is the order a reader needs: what failed,
    what the model did, how we know, then the evidence.

    Args:
        root (Path): The repository root.
        engine (str): The engine being reported.
        entry (dict): One register entry.
        pairs (dict): Case name to its task and rule set.
        tasks (dict): Task identifier to its definition.

    Returns:
        list[str]: Markdown lines for this finding.
    """
    case = str(entry.get("case", ""))
    task_id, rule_id = pairs.get(case, ("", ""))
    responses = recorded_observations(root, engine, task_id, rule_id)
    request = recorded_request(root, engine, task_id, rule_id)
    task = tasks.get(task_id)

    try:
        rules = case_for(task_id, rule_id).golden_rules
    except (KeyError, ValueError):
        rules = None
    observed = _observed(root, engine, (task_id, rule_id), rules, len(responses))

    out = [heading(case), "", *_claim_lines(entry, task, rules, observed[:2])]
    out.extend(_input_block(task, request))
    out.extend(_output_block(engine, responses, *observed))
    out.extend(["**Expected**", "", expected_block(task_id, rule_id, task), ""])
    out.extend(_reproduce_block(engine, request, case))
    out.extend([
        "| | |",
        "|---|---|",
        f"| Model | `{entry.get('observed_model', '')}` |",
        f"| Failure class | `{entry.get('taxonomy_code', '')}` |",
        f"| First observed | {entry.get('first_observed', '')} |",
        f"| Last observed | {entry.get('last_observed', '')} |",
    ])
    if str(entry.get("observations") or "").strip():
        out.append(f"| Population | {entry.get('observations')} |")
    out.extend([f"| Task | `{task_id}` |", "", "---", ""])
    return out


def _observed(
    root: Path, engine: str, pair: tuple[str, str], rules: Any, count: int
) -> tuple[list[tuple[int, bool, str]], list[Optional[tuple[bool, float, str]]], list[str]]:
    """Return how each recorded observation came out, and the prompt its judge received.

    Args:
        root (Path): The repository root.
        engine (str): The engine being reported.
        pair (tuple): The task and rule set identifiers.
        rules (Any): The case's golden rule set, or None.
        count (int): How many observations were recorded.

    Returns:
        tuple: Each observation's check outcome, its judged outcome, and its
        judge prompt, empty where the judge never saw it (section 9.5.5.8).
    """
    task_id, rule_id = pair
    stored = recorded_judgements(root, engine, task_id, rule_id, count)
    recordings = recorded_responses(root, engine, task_id, rule_id)
    return (
        observation_outcomes(task_id, rule_id, recordings),
        [judged_outcome(judgement, getattr(rules, "rubric", None)) for judgement in stored],
        judge_prompts(task_id, rule_id, recordings, stored),
    )


def _claim_lines(
    entry: dict[str, Any],
    task: Optional[dict[str, Any]],
    rules: Any,
    observed: tuple[list[tuple[int, bool, str]], list[Optional[tuple[bool, float, str]]]],
) -> list[str]:
    """Return a finding's problem, why it fails, and its diagnosis.

    Args:
        entry (dict): The register entry.
        task (Optional[dict]): The task the finding was measured on.
        rules (Any): The case's golden rule set, or None when unresolved.
        observed (tuple): Each observation's check outcome, and its judged
            outcome.

    Returns:
        list[str]: Markdown lines. **Why it fails** sits between the problem
        and the evidence, since a check firing is not yet a reason
        (section 9.5.5.6).
    """
    out = [f"**Problem:** {_issue_sentence(entry, task)}", ""]
    reasons = failure_reasons(rules, task, *observed) if rules is not None else []
    if reasons:
        out.extend(["**Why it fails:**", "", *(f"- {reason}" for reason in reasons), ""])
    diagnosis = _diagnosis(entry)
    if diagnosis:
        out.extend([f"**Diagnosis:** {diagnosis}", ""])
    return out


def _issue_sentence(entry: dict[str, Any], task: Optional[dict[str, Any]]) -> str:
    """Return the problem in the words a reader outside this project would use.

    **Not the assertion text.** That reads like instrumentation and belongs
    under Diagnosis; this is the claim the reader is being asked to accept.

    Args:
        entry (dict): The register entry.
        task (Optional[dict]): The task, for the requirement it was measured
            against.

    Returns:
        str: The sentence.
    """
    code = str(entry.get("taxonomy_code") or "")
    # WHERE THE PAYLOAD SITS DECIDES THE CLAIM (section 9.5.5.3).
    stated = framed_problem(code, task) or _PROBLEM.get(code)
    if stated is None:
        # AN UNMAPPED CODE FALLS BACK RATHER THAN INVENTING A PHRASE, and says
        # which code it could not phrase so the gap is visible.
        return _sentence(f"{code}: {entry.get('actual', '')}")

    measured = ""
    constraints = [
        item for item in ((task or {}).get("constraints") or [])
        if isinstance(item, dict) and item.get("text")
    ]
    if constraints:
        measured = (
            f" It was measured against: {constraints[0].get('text')}."
        )

    population = str(entry.get("observations") or "").strip()
    frequency = ""
    if population:
        frequency = (
            f" This happened on some attempts and not others ({population}), "
            f"so a single sample would not have shown it."
        )
    return f"{_sentence(stated)}{measured}{frequency}"


def _sentence(text: str) -> str:
    """Return text punctuated as a sentence.

    **The register's fields are phrases, not sentences.** A requirement reads
    "Understating a sourced value is permitted where instructed; overstating is
    not" with no stop, and two such phrases concatenated run together.

    Args:
        text (str): The phrase.

    Returns:
        str: The same text ending in a full stop, or empty when there was none.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped if stripped[-1] in ".!?" else f"{stripped}."


def page_for(root: Path, engine: str) -> tuple[str, list[tuple[dict[str, Any], list[str]]]]:
    """Return the ticket page for one engine, and each filed finding's section.

    Args:
        root (Path): The repository root.
        engine (str): The engine to report.

    Returns:
        tuple: Markdown with one section per finding, and each filed finding
        paired with its section for a ticket of its own (section 9.5.5.2).
    """
    register = root / "config" / "findings" / f"{engine}.yaml"
    if not register.is_file():
        return f"# {engine}\n\nNo findings register.\n", []

    payload = yaml.safe_load(register.read_text(encoding="utf-8")) or {}
    # WITHDRAWN FINDINGS ARE EXCLUDED, being claims we retracted (section
    # 9.4.1), and a finding the latest run did not observe waits apart
    # (section 9.5.5.1).
    findings, awaiting = to_file(list(payload.get("findings") or []))
    pairs = case_rules_from_suite(root)
    tasks = load_tasks(root)

    out = [
        # THE MARK FIRST, so a page is identifiable as generated and removable
        # as one (section 9.5.5.11). The tickets and the sheet carried it and
        # the pages were the one generated file a reader could not tell.
        GENERATED_MARK,
        "",
        f"# Findings against `{engine}`",
        "",
        f"**{len(findings)} finding(s).** Generated by `tools/ticket_report.py` "
        f"from `config/findings/{engine}.yaml`, the shipped corpus and the "
        f"committed recordings.",
        "",
        "Every finding below reproduces from this repository with no credential "
        "and no cost, the recordings being committed. Each section carries the "
        "exact request, every recorded response, and what was expected.",
        "",
        "---",
        "",
    ]

    sections = [(entry, finding_section(root, engine, entry, pairs, tasks))
                for entry in findings]
    for _, lines in sections:
        out.extend(lines)
    if awaiting:
        out.extend(["## Awaiting measurement", "",
                    "Open, and not observed on the latest run, so not filed:", ""])
        out.extend(f"- `{entry.get('case', '')}`, last observed "
                   f"{entry.get('last_observed', '')}" for entry in awaiting)
        out.append("")
    return "\n".join(out), sections


def main(argv: Optional[list[str]] = None) -> int:
    """Write one page per engine, and the filing sheet across them.

    Args:
        argv (Optional[list]): Arguments, or None to read from the command line.

    Returns:
        int: Zero on success.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", default="", help="One engine, or all when absent")
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    parsed = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    chosen = (parsed.engine,) if parsed.engine else _ENGINES
    parsed.out_dir.mkdir(parents=True, exist_ok=True)

    filed: dict[str, list[dict[str, Any]]] = {}
    for engine in chosen:
        page, sections = page_for(root, engine)
        filed[engine] = [entry for entry, _ in sections]
        # PRUNED FIRST, EVEN WITH NOTHING TO FILE, so an engine whose findings
        # were all withdrawn loses the tickets it used to have and the
        # directory is empty for the removal below.
        tickets = write_tickets(parsed.out_dir / engine, engine, sections)
        if not sections:
            # NO FINDING, NO OUTPUT (section 9.5.5.11). The sheet still carries
            # the engine, its zero being a measurement where a page saying zero
            # is an artifact of generation.
            for gone in drop_engine_output(parsed.out_dir, engine):
                print(f"{gone}: removed, {engine} has no filed finding")
            continue
        written = parsed.out_dir / page_name(engine)
        written.write_text(page, encoding="utf-8", newline="\n")
        print(f"{written}: written, with {len(tickets)} ticket(s) in {engine}/")

    # THE SHEET IS WRITTEN ONLY BY A RUN THAT SAW EVERY ENGINE, because its
    # total is a claim about all of them and a single-engine run would restate
    # that total from one (section 9.5.5.10).
    if set(chosen) == set(_ENGINES):
        sheet = parsed.out_dir / "FILING.md"
        sheet.write_text(filing_sheet(date.today().isoformat(), filed),
                         encoding="utf-8", newline="\n")
        print(f"{sheet}: written, with {sum(len(rows) for rows in filed.values())} "
              f"finding(s)")
    else:
        print("FILING.md not written: its total covers every engine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
