# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The apparatus the harness-pin cases assert against.

Specified by the harness ``test_taxonomy.md`` section 13.

**Extracted 2026-10-05**, when the case module stood at 995 lines against the
thousand-line ceiling with five lines of headroom. Two kinds of thing live
here: the GitHub API shapes the resolver reads, and the README figure
recomputation, which is a registry of eleven figures rather than a check.

**Public names, deliberately.** A support module is an interface, and a leading
underscore on something another module imports says the opposite of what is
true.

**`_root` is gone rather than moved.** It was the fourth byte-identical copy of
``graded_support.repository_root``, one per case module, which is what the
absence of this convention cost: a helper nobody owned was cheaper to rewrite
than to find.
"""

import ast
import csv
import re
from pathlib import Path
from typing import Any

import yaml

from ingestion.loaders import load_tasks_from_yaml
from tools import harness_pin

from tests.cases.graded_support import repository_root


# A HARNESS COMMIT, as the API spells one. The value is arbitrary and the
# width is not: the resolver truncates it for its messages.
PINNED_SHA = "d793908f3325e109da63fc05e1ddd1f2329c3f0f"


REQUIRED_WORKFLOW = "gate-on-change.yml"


WORKFLOW = "gate-on-change.yml"


SHA = "a" * 40


OTHER_SHA = "b" * 40


def workflow_run(
    sha: str = SHA,
    workflow: str = WORKFLOW,
    status: str = "completed",
    conclusion: str = "success",
    run_number: int = 1,
) -> dict[str, object]:
    """Build one workflow run as the GitHub API returns it.

    Args:
        sha (str): The commit the run executed on.
        workflow (str): The workflow filename.
        status (str): ``queued``, ``in_progress`` or ``completed``.
        conclusion (str): The concluded result.
        run_number (int): Which attempt this was.

    Returns:
        dict: The run record.
    """
    return {
        "head_sha": sha,
        "path": f".github/workflows/{workflow}",
        "status": status,
        "conclusion": conclusion,
        "run_number": run_number,
    }


def unconcluded_runs() -> list[dict[str, Any]]:
    """Return the API shape of a run that has not concluded.

    Returns:
        list[dict]: One in-progress run for the pinned commit.
    """
    return [
        {
            "head_sha": PINNED_SHA,
            "path": f".github/workflows/{REQUIRED_WORKFLOW}",
            "run_number": 1,
            "status": "in_progress",
            "conclusion": None,
        }
    ]


def concluded_runs(conclusion: str) -> list[dict[str, Any]]:
    """Return the API shape of a run that has finished.

    Args:
        conclusion (str): What it concluded.

    Returns:
        list[dict]: One completed run for the pinned commit.
    """
    return [
        {
            "head_sha": PINNED_SHA,
            "path": f".github/workflows/{REQUIRED_WORKFLOW}",
            "run_number": 1,
            "status": "completed",
            "conclusion": conclusion,
        }
    ]


def drive_wait(
    sequence: list[list[dict[str, Any]]], timeout: float = 600.0
) -> tuple[Any, int, float]:
    """Run the wait against scripted answers, spending no wall clock.

    **The clock and the sleep are injected**, so a case that exercises a ten
    minute timeout finishes instantly and asserts the interval rather than
    enduring it.

    Args:
        sequence (list): One list of runs per poll, the last repeated.
        timeout (float): The wait budget.

    Returns:
        tuple: The verdict, how many times the API was polled, and how long the
        wait believed it had spent.
    """
    remaining = list(sequence)
    polls = 0
    now = [0.0]

    def fetch(_repository: str, _commit: str, _token: Any) -> list[dict[str, Any]]:
        nonlocal polls
        polls += 1
        return remaining.pop(0) if len(remaining) > 1 else remaining[0]

    original = harness_pin.fetch_runs
    harness_pin.fetch_runs = fetch
    try:
        verdict = harness_pin.await_verdict(
            "apolskiy/AP-Harness-QC", PINNED_SHA, None, REQUIRED_WORKFLOW,
            harness_pin.WaitPolicy(
                timeout_sec=timeout, interval_sec=15.0,
                monotonic=lambda: now[0],
                delay=lambda seconds: now.__setitem__(0, now[0] + seconds),
            ),
        )
    finally:
        harness_pin.fetch_runs = original
    return verdict, polls, now[0]


def inventoried_case_ids() -> frozenset[str]:
    """Return every case identifier this repository inventories.

    Returns:
        frozenset[str]: The five-digit identifiers named by collected case
        callables. **Read from the tests rather than from a design table**,
        because a referent points at a case that exists, and the inventory
        tables are already checked against the tests elsewhere.
    """
    found: set[str] = set()
    for source in (repository_root() / "tests").rglob("mqc_*.py"):
        text = source.read_text(encoding="utf-8")
        found.update(re.findall(r"def MQC_[A-Z]+_[A-Z]+_(\d{6})_", text))
    return frozenset(found)


def open_findings(registers: list[Path], code: str = "") -> int:
    """Return how many findings are open, optionally of one failure class.

    **A withdrawn or resolved entry is excluded.** A withdrawn one records a
    claim made and retracted because our own assertion was wrong, and counting
    it would keep a retraction in a total a reader reads as current.

    **Parsed rather than counted as substrings.** A withdrawn entry still
    carries ``- case:`` and its original taxonomy code, so an occurrence count
    cannot tell a live claim from a retracted one.

    Design: ``consumer_ci.md`` section 9.4.1.

    Args:
        registers (list): The per-engine register files.
        code (str): A taxonomy code to restrict the count to, or empty for all.

    Returns:
        int: The count of open findings.
    """
    total = 0
    for register in registers:
        payload = yaml.safe_load(register.read_text(encoding="utf-8")) or {}
        for entry in payload.get("findings") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") in ("withdrawn", "resolved_upstream"):
                continue
            if code and entry.get("taxonomy_code") != code:
                continue
            total += 1
    return total


def findings_with_population(registers: list[Path]) -> int:
    """Return how many open findings record a disagreement population.

    **This is the figure the three-observation method earns, and it is not the
    count of findings classified as inconsistent.** Since 2026-10-05 a finding
    is named by the most critical code that fired, so a model that obeyed an
    injected instruction on two of five attempts is classified
    `QC_LLM_INJECTION_SUSCEPTIBLE` and carries "2 of 5 passed" as its
    population. The classification moved; what repeat observation exposed did
    not.

    Design: ``consumer_ci.md`` section 9.8.

    Args:
        registers (list): The per-engine register files.

    Returns:
        int: Open findings whose population field is set.
    """
    total = 0
    for register in registers:
        payload = yaml.safe_load(register.read_text(encoding="utf-8")) or {}
        for entry in payload.get("findings") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("status") != "open":
                continue
            if str(entry.get("observations") or "").strip():
                total += 1
    return total


def readme_figures(root: Path) -> list[tuple[str, str, int]]:
    """Return every README figure with the pattern stating it and its real value.

    **Recomputed, never stored.** A second copy of a number is what drifted in
    the first place, which is the defect this whole check exists for.

    **Extracted from the case on 2026-10-05**, when a tenth figure took it past
    the local-variable ceiling. The ceiling was right: the case was accumulating
    one bespoke computation per figure, and the list is the thing that grows.

    Args:
        root (Path): The repository root.

    Returns:
        list[tuple]: Label, a regex whose first group is the stated number, and
        the actual count.
    """
    findings = sorted((root / "config" / "findings").glob("*.yaml"))
    corpora = sorted((root / "data" / "tasks").glob("*.yaml"))
    replay = root / "tests" / "fixtures" / "replay"
    graded = graded_case_count(root)

    with (root / "docs" / "testing" / "rtm_model.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        traced = len(list(csv.DictReader(handle)))

    return [
        (
            "preconditions",
            r"\*\*(\d+) cases, all passing\*\*",
            inventoried_precondition_count(root),
        ),
        ("requirements", r"\| (\d+) requirements, traced \|", traced),
        ("graded cases", r"\*\*(\d+) written\*\*", graded),
        # THE SAME COUNT, A DIFFERENT CLAIM, and the one a reader of the front
        # page is actually asking about: how many cases each model faces.
        ("cases per model", r"\*\*(\d+) graded cases against each model\*\*", graded),
        (
            "recorded engines",
            r"\*\*(\d+) engines recorded\*\*",
            sum(
                1 for engine in sorted(replay.glob("*"))
                if engine.is_dir() and engine.name != "judgements"
            ),
        ),
        (
            "candidate responses",
            r"\*\*(\d+) candidate responses\*\*",
            sum(
                1
                for engine in sorted(replay.glob("*"))
                if engine.is_dir() and engine.name != "judgements"
                for recorded in engine.rglob("*")
                if recorded.is_file()
            ),
        ),
        (
            "judgements",
            r"\*\*(\d+) judgements\*\*",
            sum(1 for path in (replay / "judgements").rglob("*") if path.is_file()),
        ),
        # COUNTED FROM THE PARSED ENTRIES, NOT FROM OCCURRENCES. A substring
        # count included a withdrawn entry, which still carries `- case:` and
        # its original taxonomy code: a retracted claim would have stayed in a
        # total a reader reads as current. `consumer_ci.md` section 9.4.1.
        (
            "model findings",
            r"\*\*(\d+) findings\*\*",
            open_findings(findings),
        ),
        # THE SUBSET THE METHOD EXISTS FOR. Stated at eleven of twenty when the
        # README was written against three engines, and grok's recording made it
        # fourteen of twenty-four without anybody touching the sentence.
        # THE POPULATION, NOT THE CLASSIFICATION. Stated as a count of
        # findings classified `QC_LLM_INCONSISTENT` until 2026-10-05, when
        # findings began carrying their most critical code and eleven of the
        # twelve reclassified. **What repeat observation exposed did not
        # change**; only the name on each finding did.
        (
            "findings exposed by repeat observation",
            r"\*\*(\d+) of the 23 findings carry a disagreement population\*\*",
            findings_with_population(findings),
        ),
        (
            "findings classified as inconsistency",
            r"\*\*(\d+) is classified as inconsistency\*\*",
            open_findings(findings, "QC_LLM_INCONSISTENT"),
        ),
        ("corpora", r"\*\*(\d+) corpora", len(corpora)),
        (
            "tasks",
            r"\*\*\d+ corpora, (\d+) tasks\*\*",
            sum(len(load_tasks_from_yaml(source)) for source in corpora),
        ),
    ]


def inventoried_precondition_count(root: Path) -> int:
    """Return the precondition total the design documents inventory.

    Args:
        root (Path): The repository root.

    Returns:
        int: The sum of every stated inventory.
    """
    total = 0
    for document in sorted((root / "docs").rglob("*.md")):
        stated = re.search(
            r"^\*\*Inventory:\s*(\d+)\s+cases",
            document.read_text(encoding="utf-8"),
            re.M,
        )
        if stated is not None:
            total += int(stated.group(1))
    return total


def graded_case_count(root: Path) -> int:
    """Return the number of graded cases this repository defines.

    **Parsed rather than matched**, so a name inside a string literal is data.

    Args:
        root (Path): The repository root.

    Returns:
        int: The count of graded case callables.
    """
    graded = 0
    for source in sorted((root / "tests" / "cases").glob("*.py")):
        if source.stem.startswith("mqc_uni_") or source.stem == "graded_support":
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        graded += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("MQC_")
        )
    return graded
