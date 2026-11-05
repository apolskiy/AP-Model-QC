# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading which corpus case each graded case observes, from the suite itself.

Created: 2026-10-21
Last updated: 2026-11-05

This file contains ``case_rules_from_suite``, which parses every graded case module
and returns the task and rule set each case dispatches through ``observe`` or
``observe_repeatedly``, ``case_families_from_suite``, which returns the
evaluation family each case's rule set declares, and
``planted_mixed_population``, which builds a finding whose observations split
into judged and unjudged from a copy of one case's recordings.

The priority agreement and family preconditions, the case index and the ticket
tools call them, so a case is tied to its corpus entry by the call it makes rather
than by a list somebody keeps. Moved out of ``graded_support.py`` on 2026-10-21,
when that module reached the 900-line runway (harness ``code-style.md`` section 5.1).
"""

import ast
import json
import shutil
from pathlib import Path
from typing import Any, Final, Optional

from tests.cases.graded_support import engine_roster, shipped_corpus
from tools.ticket_recordings import observation_outcomes, recorded_responses

# A CASE'S DISPATCH CALL, whose second and third string arguments name the task
# and the rule set it observes. Parsed rather than matched, because a regex over
# source lines also matches a docstring quoting the call.
_OBSERVERS: Final[frozenset[str]] = frozenset({"observe", "observe_repeatedly"})


def case_rules_from_suite(root: Path) -> dict[str, tuple[str, str]]:
    """Return the task and rule set each graded case dispatches.

    **The link nothing declared.** A case names its task and rule in the
    dispatch call it makes, and that is the only place the pairing exists; the
    matrix knows requirements and the corpus knows families, and neither knows
    which case observes which pair.

    Parsed rather than matched, because a regex over source lines also matches
    a docstring quoting the call.

    Args:
        root (Path): This repository's root.

    Returns:
        dict[str, tuple[str, str]]: Case name to its task and rule identifier.
        **A case that dispatches nothing is absent** rather than defaulted: a
        precondition performs no task.
    """
    tasks, rules = shipped_corpus()
    known_tasks = {entry.task_id for entry in tasks}
    known_rules = {entry.rule_id for entry in rules}

    pairs: dict[str, tuple[str, str]] = {}
    for source in sorted((root / "tests" / "cases").glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            task_id = rule_id = ""
            for inner in ast.walk(node):
                if not isinstance(inner, ast.Call):
                    continue
                called = inner.func
                name = getattr(called, "id", None) or getattr(called, "attr", None)
                if name not in _OBSERVERS:
                    continue
                for entry in inner.args:
                    if not isinstance(entry, ast.Constant) or not isinstance(
                        entry.value, str
                    ):
                        continue
                    if entry.value in known_tasks:
                        task_id = entry.value
                    elif entry.value in known_rules:
                        rule_id = entry.value
            if task_id and rule_id:
                pairs[node.name] = (task_id, rule_id)
    return pairs


def case_families_from_suite(root: Path) -> dict[str, str]:
    """Return each graded case's primary evaluation family.

    **The link a matrix check has been missing.** T5 compares a matrix row's
    ``families`` against the families of the cases the row names, and it takes
    that mapping as an argument; nothing could build one until a rule set
    declared its families on 2026-10-04. Harness ``harness_test_taxonomy.md`` sections
    11.4.2 and 11.8.3.

    Args:
        root (Path): This repository's root.

    Returns:
        dict[str, str]: Case name to its primary family, omitting a case whose
        rule set declares none.
    """
    family_by_rule = {
        rules.rule_id: rules.families[0]
        for rules in shipped_corpus()[1] if rules.families
    }
    return {
        case: family_by_rule[rule_id]
        for case, (_, rule_id) in case_rules_from_suite(root).items()
        if rule_id in family_by_rule
    }


def planted_mixed_population(
    root: Path, scratch: Path, suite: dict[str, tuple[str, str]]
) -> Optional[tuple[str, dict, list[int], list[int], int]]:
    """Return a finding whose observations split into judged and unjudged, built under scratch.

    Copies one judged case's recordings and judgements into ``scratch`` and
    rewrites its last response to the passage its ``source_phrase_absent``
    check forbids, so that observation fails the check and the others reach
    the judge. The population is planted rather than found, since which case
    holds one moves with every recording and every gate (``consumer_ci.md``
    section 9.4.10).

    Args:
        root (Path): This repository's root, read only.
        scratch (Path): The root the planted recordings are written under.
        suite (dict[str, tuple[str, str]]): Each case's task and rule.

    Returns:
        Optional[tuple[str, dict, list[int], list[int], int]]: The engine, a
        register entry naming the case, the judged indices, the unjudged
        indices and the population measured, or None where no judged case
        declaring the check holds two recordings.
    """
    forbidden = {
        rules.rule_id: check
        for rules in shipped_corpus()[1] if rules.rubric is not None
        for check in rules.assertions if check.kind == "source_phrase_absent"
    }
    for engine in engine_roster():
        for case, pair in sorted(suite.items()):
            if pair[1] not in forbidden:
                continue
            outcomes = _plant(root, scratch, (engine, *pair), forbidden[pair[1]])
            judged = [index for index, passed, _ in outcomes if passed]
            unjudged = [index for index, passed, _ in outcomes if not passed]
            if judged and unjudged:
                entry = {"case": case, "taxonomy_code": forbidden[pair[1]].taxonomy_code}
                return (engine, entry, judged, unjudged, len(outcomes))
    return None


def _plant(
    root: Path, scratch: Path, where: tuple[str, str, str], check: Any
) -> list[tuple[int, bool, str]]:
    """Copy one pair's recordings and judgements, plant the passage in the last, and check them.

    Args:
        root (Path): This repository's root, read only.
        scratch (Path): The root the copies are written under.
        where (tuple[str, str, str]): The engine, the task and the rule set.
        check (Any): The ``source_phrase_absent`` assertion whose source is planted.

    Returns:
        list[tuple[int, bool, str]]: Each copied observation's check outcome,
        empty where the pair holds fewer than two recordings.
    """
    engine, task_id, rule_id = where
    replay = Path("tests") / "fixtures" / "replay"
    recordings = root / replay / engine / task_id / rule_id
    if len(list(recordings.glob("*.json"))) < 2:
        return []
    planted = scratch / replay / engine / task_id / rule_id
    shutil.copytree(recordings, planted, dirs_exist_ok=True)
    for judged_by in (root / replay / "judgements" / engine).glob(f"*/{task_id}/{rule_id}"):
        shutil.copytree(judged_by, scratch / judged_by.relative_to(root), dirs_exist_ok=True)
    target = max(planted.glob("*.json"), key=lambda path: int(path.stem))
    record = json.loads(target.read_text(encoding="utf-8"))
    record["response"]["text"] = check.parameters["source"]
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return observation_outcomes(
        task_id, rule_id, recorded_responses(scratch, engine, task_id, rule_id))
