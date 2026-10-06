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


def _section(
    root: Path,
    engine: str,
    entry: dict[str, Any],
    pairs: dict[str, tuple[str, str]],
    tasks: dict[str, dict[str, Any]],
) -> list[str]:
    """Return the markdown for one finding.

    **Separated from ``page_for`` on 2026-10-05**, when a tenth rendered field
    took that function past the local-variable ceiling. The division is the one
    the ceiling suggested: this renders a finding, that assembles a page.

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
        f"| Reproduce | `{entry.get('reproduce', '')}` |",
        "",
        f"**Expected.** {entry.get('expected', '')}",
        "",
        f"**Observed.** {entry.get('actual', '')}",
        "",
        "### The request",
        "",
        _request_block(tasks.get(task_id)),
        "### What the model returned",
        "",
    ])
    if not responses:
        out.append(
            f"_No recording found at "
            f"`tests/fixtures/replay/{engine}/{task_id}/{rule_id}/`._\n"
        )
    for index, text in enumerate(responses):
        label = (
            f"Observation {index + 1} of {len(responses)}"
            if len(responses) > 1
            else "Response"
        )
        out.extend([
            f"**{label}**\n",
            "```",
            text.rstrip() or "[empty response]",
            "```\n",
        ])
    out.extend(["---", ""])
    return out


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
    findings = payload.get("findings") or []
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
