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

from tests.cases.graded_support import case_rules_from_suite

_DEFAULT_OUT: Final[Path] = Path("reports") / "tickets"
_ENGINES: Final[tuple[str, ...]] = ("gemini", "openai", "claude", "grok")


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


def _frequency(entry: dict[str, Any], responses: list[str]) -> str:
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
    population = str(entry.get("observations") or "").strip()
    if population:
        parts = population.split()
        if len(parts) >= 3 and parts[0].isdigit() and parts[2].isdigit():
            passed, total = int(parts[0]), int(parts[2])
            return f"{total - passed} out of {total} times"
    if responses:
        return f"on each of {len(responses)} observations" if len(
            responses
        ) > 1 else "on the single observation taken"
    return "on an observation this report could not locate"


def _steps(
    engine: str,
    entry: dict[str, Any],
    task: Optional[dict[str, Any]],
    responses: list[str],
) -> list[str]:
    """Return the detail, then every failing output, then the reproduction.

    **Ordered as feedback reads**, per section 9.5.1: the scenario and its
    detail, then what the engine produced and how often, then how to see it
    again. The earlier version numbered steps and repeated the same expected
    and actual pair against each observation, which stated the requirement
    five times and the finding once.

    Args:
        engine (str): The engine under test.
        entry (dict): The register entry.
        task (Optional[dict]): The task definition.
        responses (list): Each recorded observation's text.

    Returns:
        list[str]: Markdown lines.
    """
    out = ["### The scenario, in detail", ""]
    if task is None:
        out.extend(["_The task could not be resolved._", ""])
    else:
        out.extend(["**What was asked**", "", "```",
                    str(task.get("user_prompt", "")).rstrip(), "```", ""])
        constraints = task.get("constraints") or []
        if constraints:
            out.extend(["**What it was told not to do**", ""])
            for item in constraints:
                if isinstance(item, dict):
                    out.append(
                        f"- `{item.get('constraint_id', '')}` "
                        f"({item.get('kind', '')}): {item.get('text', '')}"
                    )
            out.append("")
        documents = task.get("context_documents") or []
        if documents:
            out.extend(["**What it was given to work from**", ""])
            for item in documents:
                if not isinstance(item, dict):
                    continue
                out.append(f"*{item.get('title', item.get('document_id', ''))}*")
                out.extend(["", "```",
                            str(item.get("content", "")).rstrip(), "```", ""])

    failing = [body for body in responses if body.strip()]
    out.extend([
        f"### What `{entry.get('observed_model', '')}` produced",
        "",
        f"**It failed {_frequency(entry, responses)}.** Every observation taken "
        f"is shown, because a ratio cannot be read from one of them.",
        "",
    ])
    if not failing:
        out.extend(["_No recording was located for this case._", ""])
    for index, body in enumerate(failing):
        label = (
            f"Observation {index + 1} of {len(failing)}"
            if len(failing) > 1 else "The response"
        )
        out.extend([f"**{label}**", "", "```", body.rstrip(), "```", ""])

    out.extend([
        "### Seeing it again",
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
    ])
    return out


def _section(
    root: Path,
    engine: str,
    entry: dict[str, Any],
    pairs: dict[str, tuple[str, str]],
    tasks: dict[str, dict[str, Any]],
) -> list[str]:
    """Return the defect report for one finding.

    **Case, then issue, then steps**, per section 9.5.1. The earlier layout put
    the metadata table first and the request and responses in separate later
    blocks, which stated everything and followed nothing.

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

    out = [
        f"## `{case}`",
        "",
        f"**During this scenario:** {_scenario(tasks.get(task_id))}.",
        "",
        f"**Expected:** {_sentence(entry.get('expected', ''))}",
        "",
        f"**`{entry.get('observed_model', '')}` produced a failing output "
        f"{_frequency(entry, responses)}:** {_issue_sentence(entry)}",
        "",
        "| | |",
        "|---|---|",
        f"| Model | `{entry.get('observed_model', '')}` |",
        f"| Failure class | `{entry.get('taxonomy_code', '')}` |",
        f"| First observed | {entry.get('first_observed', '')} |",
        f"| Last observed | {entry.get('last_observed', '')} |",
    ]
    if str(entry.get("observations") or "").strip():
        out.append(f"| Consistency | {entry.get('observations')} |")
    out.extend([
        f"| Task | `{task_id}` |",
        "",
    ])

    if not responses:
        out.extend([
            f"_No recording found at "
            f"`tests/fixtures/replay/{engine}/{task_id}/{rule_id}/`, so the steps "
            f"below cannot carry what was returned._",
            "",
        ])
    out.extend(_steps(engine, entry, tasks.get(task_id), responses))
    out.extend(["---", ""])
    return out


def _issue_sentence(entry: dict[str, Any]) -> str:
    """Return the one sentence stating what went wrong.

    **Separated from the requirement it follows**, because the two are different
    claims: the first is what should hold and the second is what was seen.

    Args:
        entry (dict): The register entry.

    Returns:
        str: The sentence.
    """
    observations = str(entry.get("observations") or "").strip()
    if observations:
        return (
            f"The requirement does not hold consistently: {observations}, so "
            f"no single sample from this model characterises its behaviour "
            f"here."
        )
    return _sentence(str(entry.get("actual", "")))


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
