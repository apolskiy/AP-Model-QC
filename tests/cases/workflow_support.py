# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading the CI workflow definitions, for the cases that check them.

Created: 2026-10-03
Last updated: 2026-10-21

This file contains ``load``, ``jobs`` and ``needs``, which parse a workflow and its job
graph; ``run_lines``, which returns each step's run body, following a local ``uses:``;
``selects_a_graded_marker`` and ``graded_invocations``, which find the pytest calls that
run graded cases; ``floor_conditions`` and ``band_action_inputs``, which read the shared
band definition; and ``cases_by_priority`` and ``repository_root``.

**``mqc_uni_workflows.py``, ``mqc_uni_engine_jobs.py`` and ``mqc_uni_band_gating.py``
import it**, all in the ``unit`` precondition gate, so every check on a workflow reads
the workflow one way.

Extracted 2026-10-03, when the engine-separation cases took
``mqc_uni_workflows.py`` past the thousand-line ceiling and two modules needed
the same readers. **A duplicated reader drifts**, and a case comparing against
a stale copy of a workflow reports about the copy.

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, which is the arrangement
``graded_support.py`` already uses.
"""

import re
from pathlib import Path
from typing import Any, Final, Optional

import yaml

WORKFLOWS: Final[Path] = Path(__file__).resolve().parents[2] / ".github" / "workflows"

# The markers a graded invocation selects. "sec" is the dangerous one, being a
# substring of section, second, security and secret.
GRADED_MARKERS: Final[tuple[str, ...]] = ("evaluator", "tool", "sec")


def load(name: str) -> dict[str, Any]:
    """Return one workflow definition, parsed.

    Args:
        name (str): The filename inside the workflows directory.

    Returns:
        dict: The parsed document.
    """
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def jobs(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return a workflow's jobs.

    Args:
        workflow (dict): The parsed document.

    Returns:
        dict: Job name to its definition.
    """
    return workflow.get("jobs") or {}


def needs(job: dict[str, Any]) -> list[str]:
    """Return what a job declares it needs, however it spells it.

    Args:
        job (dict): The job definition.

    Returns:
        list[str]: The job names, which a single dependency may give as a
        string rather than a list.
    """
    declared = job.get("needs") or []
    return [declared] if isinstance(declared, str) else list(declared)


def run_lines(job: dict[str, Any], root: Optional[Path] = None) -> list[str]:
    """Return each step's run body with continuations folded, following a local uses.

    **Folded, because a graded invocation spans several lines.** A matcher
    reading raw lines would see the marker on one and the runner on another.

    **A local `uses:` is followed**, so a command factored into a composite
    action is still read as part of the job that uses it. Eight call sites read
    the pytest invocation out of a job, and a check that stops finding it
    reports agreement having read nothing: a green that means nothing was
    checked (harness `harness_ci_pipeline.md` section 8.4).

    **A third-party action is not followed.** `actions/checkout@v5` is not this
    repository's prose and its contents are not ours to assert.

    Args:
        job (dict): The job definition.
        root (Optional[Path]): The repository root, needed to resolve a local
            `uses:`. **Absent reads only the job's own steps**, which keeps
            every existing caller working and is why the parameter is optional
            rather than required.

    Returns:
        list[str]: One folded body per step that has one, the followed
        definitions' bodies included.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when a local ``uses:``
            names a path that is not there. A workflow referring to a
            definition that does not exist is broken, and returning the lines
            it did find would report on a workflow that cannot run.
    """
    folded: list[str] = []
    for step in job.get("steps") or []:
        body = str((step or {}).get("run") or "")
        if body:
            folded.append(re.sub(r"\\\s*\n\s*", " ", body))
        reference = str((step or {}).get("uses") or "")
        if root is not None and reference.startswith("./"):
            folded.extend(_referenced_run_lines(root, reference))
    return folded


def _referenced_run_lines(root: Path, reference: str) -> list[str]:
    """Return the run bodies a local `uses:` reference contributes.

    Args:
        root (Path): The repository root.
        reference (str): The ``uses:`` value, beginning with ``./``.

    Returns:
        list[str]: The referenced definition's folded run bodies.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when the reference names
            no readable definition.
    """
    target = root / reference[2:]
    candidates = (
        [target] if target.suffix in (".yml", ".yaml")
        else [target / "action.yml", target / "action.yaml"]
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        parsed = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        # A COMPOSITE ACTION KEEPS ITS STEPS UNDER `runs`; A CALLED WORKFLOW
        # KEEPS THEM UNDER EACH JOB. Both are read, because both are places a
        # command can be factored to.
        inner = [parsed.get("runs") or {}]
        inner.extend((parsed.get("jobs") or {}).values())
        bodies: list[str] = []
        for definition in inner:
            bodies.extend(run_lines(definition, root))
        return bodies
    raise ValueError(
        f"QC_HARNESS_PARSER_ERROR: a workflow uses {reference!r} and no "
        f"definition is there, so the workflow cannot run and this reader "
        f"would report on one that does not exist"
    )


def selects_a_graded_marker(line: str) -> bool:
    """Report whether a run body invokes pytest selecting a graded marker.

    Args:
        line (str): One step's run body, continuations folded.

    Returns:
        bool: True where a ``-m`` expression names a graded marker as a whole
        word. **A computed expression selects nothing here**, which is
        unchanged: a dispatch passing a marker through an input never carried a
        literal one to match.
    """
    if "pytest" not in line:
        return False
    for quoted, bare in re.findall(r'-m\s+(?:"([^"]*)"|(\S+))', line):
        selected = quoted or bare
        if any(
            re.search(rf"\b{re.escape(marker)}\b", selected)
            for marker in GRADED_MARKERS
        ):
            return True
    return False


def graded_invocations(
    job: dict[str, Any], root: Optional[Path] = None
) -> list[str]:
    """Return every graded invocation a job makes.

    Args:
        job (dict): The job definition.
        root (Optional[Path]): The repository root, so a local ``uses:`` is
            followed (harness `harness_ci_pipeline.md` section 8.4).

    Returns:
        list[str]: The folded run bodies that select a graded marker.
    """
    return [
        line for line in run_lines(job, root)
        if selects_a_graded_marker(line)
    ]


def floor_conditions(root: Path) -> list[str]:
    """Return the condition on each floor step in the shared band definition.

    **The step lives in the definition, not in the job.** A job names its band
    and the definition owns the procedure, so a reader asking whether a floor
    runs on a red band asks the definition (`consumer_ci.md` section 3.12.7).

    Args:
        root (Path): The repository root.

    Returns:
        list[str]: One condition per step invoking the floor, empty where the
        definition invokes it nowhere.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when the definition is
            absent. A caller asking about a definition that is not there must
            not be told there are no floor steps.
    """
    definition = root / ".github" / "actions" / "band" / "action.yml"
    if not definition.is_file():
        raise ValueError(
            f"QC_HARNESS_PARSER_ERROR: {definition} is absent, so no band "
            f"definition could be read and its floor steps cannot be assessed"
        )
    parsed = yaml.safe_load(definition.read_text(encoding="utf-8")) or {}
    return [
        str(step.get("if", ""))
        for step in (parsed.get("runs") or {}).get("steps") or []
        if "band_floor" in str(step.get("run", ""))
    ]


def repository_root() -> Path:
    """Return this repository's root.

    **Needed so a reader follows a local `uses:`.** A command factored into a
    composite action is still the job's command, and a reader without the root
    finds neither it nor anything else that moves later (harness
    `harness_ci_pipeline.md` section 8.4).

    Returns:
        Path: The root, three levels above this module.
    """
    return Path(__file__).resolve().parents[2]


# THE ONE BAND DEFINITION EVERY GRADED JOB CALLS, named once so a case and a
# workflow cannot disagree about where it lives (`consumer_ci.md` 3.12.7).
BAND_ACTION: Final[str] = "./.github/actions/band"

# WHERE A BAND SPLITS. A band job selecting more than this many cases becomes
# its own priorities: one threshold rather than a runway and a ceiling, because
# a band job's size changes only when somebody adds a case.
BAND_CASE_CEILING: Final[int] = 1000


def band_action_inputs(root: Path) -> dict[str, Any]:
    """Return the inputs the shared band definition declares.

    Args:
        root (Path): The repository root.

    Returns:
        dict[str, Any]: Input name to its declaration.

    Raises:
        ValueError: With ``QC_HARNESS_PARSER_ERROR`` when the definition is
            absent, so a caller is never told it declares no inputs.
    """
    definition = root / ".github" / "actions" / "band" / "action.yml"
    if not definition.is_file():
        raise ValueError(
            f"QC_HARNESS_PARSER_ERROR: {definition} is absent, so the band "
            f"definition declares nothing a caller could be checked against"
        )
    parsed = yaml.safe_load(definition.read_text(encoding="utf-8")) or {}
    return dict(parsed.get("inputs") or {})


def cases_by_priority() -> dict[int, int]:
    """Return how many graded cases each priority holds.

    **Read from the shipped corpus**, so the count a band job selects is the
    count it will actually select rather than a figure stored beside it.

    Returns:
        dict[int, int]: Priority to case count, priorities with no case absent.
    """
    # IMPORTED HERE, NOT AT MODULE SCOPE. `graded_support` loads the whole
    # corpus on import, and the workflow cases that read this module do
    # not need it: paying for the corpus to check a YAML file would make
    # every workflow case slower for one caller's benefit.
    # pylint: disable=import-outside-toplevel
    from tests.cases.graded_support import shipped_cases

    counted: dict[int, int] = {}
    for case in shipped_cases().values():
        priority = getattr(case.golden_rules, "priority", None)
        if priority is None:
            continue
        counted[int(priority)] = counted.get(int(priority), 0) + 1
    return counted
