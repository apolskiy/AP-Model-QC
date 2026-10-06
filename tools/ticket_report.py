# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""One ticket-ready page per engine: the finding, the request, the responses.

Specified by ``docs/design/consumer_ci.md`` section 9.5.

**Three sources had to be joined by hand before this existed.** The findings
register carries the claim, the corpus carries the prompt, and the replay
fixtures carry what the model said; nothing carried all three, so filing a
ticket meant two lookups per finding and three more for an inconsistency.

| Source | Supplies |
|---|---|
| ``config/findings/<engine>.yaml`` | The claim, the taxonomy code, expected and actual |
| ``data/tasks/*.yaml`` | The prompt, the constraints and the context documents |
| ``tests/fixtures/replay/<engine>/`` | Every recorded observation's text |

**The request is reconstructed, not recorded.** A fixture stores a
``request_hash`` and never the prompt, so the prompt here comes from the corpus
the run dispatched. That is the same text by construction, and the hash is what
proves a replay is answering the same request.

**Every observation is shown, not just one.** An inconsistency finding is a
claim about variance, and a single transcript cannot carry it: three passes out
of five is the finding, and a reader needs all of them.

Usage::

    python -m tools.ticket_report                 # every rostered engine
    python -m tools.ticket_report --engine claude
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final, Optional

import yaml

from evaluation.assertions import run_assertions
from tests.cases.graded_support import case_for, case_rules_from_suite

_DEFAULT_OUT: Final[Path] = Path("reports") / "tickets"
_ENGINES: Final[tuple[str, ...]] = ("gemini", "openai", "claude", "grok")


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
}


def observation_outcomes(
    task_id: str, rule_id: str, responses: list[str]
) -> list[tuple[int, bool, str]]:
    """Return each observation's assertion outcome, by replaying the checks.

    **The checks are re-run rather than read from a report.** They are pure
    functions of the recorded text, so this is deterministic, needs no
    credential and costs nothing — and it lets the document say which
    observation carried the problem instead of showing five and leaving the
    reader to find it.

    **The rubric is not re-run.** It needs a judge, so an observation that
    passed every assertion is reported as such and nothing is claimed about
    its score.

    Args:
        task_id (str): The task identifier.
        rule_id (str): The rule set identifier.
        responses (list): Each recorded observation's text.

    Returns:
        list: One entry per observation, as index, whether every assertion
        passed, and what failed when one did.
    """
    try:
        case = case_for(task_id, rule_id)
    except (KeyError, ValueError):
        return []
    outcomes = []
    for index, body in enumerate(responses):
        failures = [
            f"{result.assertion_id} ({result.taxonomy_code}): {result.detail}"
            for result in run_assertions(case.golden_rules.assertions, body)
            if not result.passed
        ]
        outcomes.append((index, not failures, "; ".join(failures)))
    return outcomes


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


def recorded_observations(root: Path, engine: str, task: str, rule: str) -> list[str]:
    """Return every recorded response text for one pair, in observation order.

    Args:
        root (Path): The repository root.
        engine (str): The engine whose recordings to read.
        task (str): The task identifier.
        rule (str): The rule set identifier.

    Returns:
        list[str]: The response text of each observation. Empty when the pair
        was never recorded for this engine, which is reported rather than
        treated as an empty answer.
    """
    folder = root / "tests" / "fixtures" / "replay" / engine / task / rule
    if not folder.is_dir():
        return []
    texts: list[str] = []
    for source in sorted(folder.glob("*.json"), key=lambda path: path.name):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            texts.append("[unreadable recording]")
            continue
        texts.append(str((payload.get("response") or {}).get("text", "")))
    return texts


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
    lines = ["**Prompt**\n", "```", str(task.get("user_prompt", "")).rstrip(), "```\n"]

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
            lines.append("```")
            lines.append(str(entry.get("content", "")).rstrip())
            lines.append("```\n")
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


def _frequency(
    entry: dict[str, Any],
    responses: list[str],
    outcomes: Optional[list[tuple[int, bool, str]]] = None,
) -> str:
    """Return how often the failure occurred, in words.

    **The ratio is the finding when it is intermittent.** An attacker retries,
    so "obeyed on 2 of 5 attempts" is a security claim and "obeyed" alone
    overstates while "sometimes" understates.

    Args:
        entry (dict): The register entry.
        responses (list): The recorded observations.

    Returns:
        str: A phrase such as ``"3 out of 5 times"``.
    """
    # COUNTED FROM THE REPLAYED CHECKS FIRST, because the register's ratio is
    # the whole case's verdict and can include observations whose judgement
    # was unavailable. The checks are what this document shows, so they are
    # what it counts.
    if outcomes:
        failing = sum(1 for _, passed, _ in outcomes if not passed)
        if failing:
            return f"{failing} of {len(outcomes)} observations"
    population = str(entry.get("observations") or "").strip()
    if population:
        parts = population.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[2].isdigit():
            passed, total = int(parts[0]), int(parts[2])
            return f"{total - passed} of {total} observations"
    if responses:
        return f"on each of {len(responses)} observations" if len(
            responses
        ) > 1 else "on the single observation taken"
    return "on an observation this report could not locate"


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
    return _sentence(actual)


def _input_block(task: Optional[dict[str, Any]]) -> list[str]:
    """Return the prompt as sent, with what was supplied alongside it.

    Args:
        task (Optional[dict]): The task definition.

    Returns:
        list[str]: Markdown lines.
    """
    if task is None:
        return ["**Input**", "", "_The task could not be resolved._", ""]

    out = ["**Input**", ""]
    system = str(task.get("system_instruction") or "").strip()
    if system:
        out.extend(["*System instruction*", "", "```", system, "```", ""])
    out.extend(["*Prompt*", "", "```",
                str(task.get("user_prompt", "")).rstrip(), "```", ""])
    documents = task.get("context_documents") or []
    for item in documents:
        if not isinstance(item, dict):
            continue
        out.extend([
            f"*Supplied: {item.get('title', item.get('document_id', ''))}*",
            "", "```", str(item.get("content", "")).rstrip(), "```", "",
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


def _output_block(
    engine: str,
    entry: dict[str, Any],
    responses: list[str],
    outcomes: list[tuple[int, bool, str]],
) -> list[str]:
    """Return the observations, each labelled by what its checks found.

    **Which observation carried the problem is stated, not left to the
    reader.** Showing five responses where one failed buries the finding, and
    stating a ratio without the responses makes it unverifiable.

    Args:
        engine (str): The engine under test.
        entry (dict): The register entry.
        responses (list): Each recorded observation's text.
        outcomes (list): Per-observation assertion outcomes, possibly empty
            when the case could not be resolved.

    Returns:
        list[str]: Markdown lines.
    """
    bodies = [body for body in responses if body.strip()]
    out = [f"**Output** — the problem appeared on "
           f"{_frequency(entry, responses, outcomes)}", ""]
    if not bodies:
        out.extend([
            f"_No recording at `tests/fixtures/replay/{engine}/`, so this "
            f"finding cannot show what was returned._", "",
        ])
        return out

    verdicts = {index: (passed, detail) for index, passed, detail in outcomes}
    for index, body in enumerate(bodies):
        label = f"Observation {index + 1} of {len(bodies)}"
        if index in verdicts:
            passed, detail = verdicts[index]
            label += " — checks passed" if passed else " — this one failed"
        out.extend([f"*{label}*", "", "```", body.rstrip(), "```", ""])
        if index in verdicts and not verdicts[index][0]:
            out.extend([f"> {verdicts[index][1]}", ""])
    return out


def _section(
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
    task = tasks.get(task_id)

    out = [
        f"## Failing test case: `{case}`",
        "",
        f"**Problem:** {_issue_sentence(entry, task)}",
        "",
    ]
    diagnosis = _diagnosis(entry)
    if diagnosis:
        out.extend([f"**Diagnosis:** {diagnosis}", ""])
    out.extend(_input_block(task))
    out.extend(_output_block(
        engine, entry, responses,
        observation_outcomes(task_id, rule_id, responses),
    ))

    out.extend([
        "<details><summary>Expected behaviour, provenance and reproduction"
        "</summary>",
        "",
        f"**Expected:** {_sentence(entry.get('expected', ''))}",
        "",
        "| | |",
        "|---|---|",
        f"| Model | `{entry.get('observed_model', '')}` |",
        f"| Failure class | `{entry.get('taxonomy_code', '')}` |",
        f"| First observed | {entry.get('first_observed', '')} |",
        f"| Last observed | {entry.get('last_observed', '')} |",
    ])
    if str(entry.get("observations") or "").strip():
        out.append(f"| Population | {entry.get('observations')} |")
    out.extend([
        f"| Task | `{task_id}` |",
        "",
        "```",
        str(entry.get("reproduce", "")),
        "```",
        "",
        f"The recordings are committed, so this needs no credential and spends "
        f"nothing. It replays what `{engine}` returned on "
        f"{entry.get('first_observed', '')} rather than calling the model "
        f"again, and only a live run can establish that the behaviour has "
        f"changed since.",
        "",
        "</details>",
        "",
        "---",
        "",
    ])
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
    stated = _PROBLEM.get(code)
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


def page_for(root: Path, engine: str) -> str:
    """Return the ticket page for one engine.

    Args:
        root (Path): The repository root.
        engine (str): The engine to report.

    Returns:
        str: Markdown, one section per finding.
    """
    register = root / "config" / "findings" / f"{engine}.yaml"
    if not register.is_file():
        return f"# {engine}\n\nNo findings register.\n"

    payload = yaml.safe_load(register.read_text(encoding="utf-8")) or {}
    # WITHDRAWN FINDINGS ARE EXCLUDED. These pages exist to be filed, and a
    # withdrawn finding must not be: it records a claim we made and retracted
    # because our own assertion was wrong. Section 9.4.1.
    findings = [
        entry for entry in (payload.get("findings") or [])
        if not (isinstance(entry, dict) and entry.get("status") == "withdrawn")
    ]
    pairs = case_rules_from_suite(root)
    tasks = load_tasks(root)

    out = [
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

    for entry in findings:
        if isinstance(entry, dict):
            out.extend(_section(root, engine, entry, pairs, tasks))
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    """Write one page per engine.

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

    for engine in chosen:
        written = parsed.out_dir / f"{engine}.md"
        written.write_text(page_for(root, engine), encoding="utf-8", newline="\n")
        print(f"{written}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
