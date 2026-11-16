# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code dropping quarantined cases at collection, so no band runs or counts them.

Created: 2026-11-15
Last updated: 2026-11-16

This file contains ``quarantine_deselection``, which splits collected items
into those kept and those whose corpus case the run's engine has quarantined,
``deselect_quarantined_cases``, which ``conftest.py`` calls at collection
to set every held case aside as a foundation and drop the held cases this band
collected; ``held_case_numbers``, the case numbers of the held cases;
``note_foundation_question`` and ``foundation_questions``, which record and
return a line for each dependent that passed while its foundation is
quarantined; and ``declared_dependents``, each foundation's dependents as the
case modules declare them. For the cases it holds ``write_quarantine_file``,
``file_entry``, ``dropped_names``, ``dependent_item``,
``clear_foundation_questions``, ``called_names`` and ``top_level_calls``.

**A quarantined case is not a skip.** A skip counts as not passed in every
band; a quarantined case has a ticket against it and is being fixed at the
production team's pace, so it is neither run nor counted, at any priority.
Only an entry in force holds its case out: quarantine ends on removal, on
expiry of its window, or on a model change where the entry says so, and the
case is collected again from the next run. A quarantined foundation's
dependents run and count unless quarantined by name (section 4.14.2).

**Not a test module.** ``pytest.ini`` collects ``mqc_*.py``, so this name sits
outside that pattern deliberately, as ``workflow_support.py`` does.

Specified by harness ``cmn_verdict_and_cli.md`` section 4.6.14 and
``docs/design/consumer_ci.md`` section 3.12.2.
"""

import ast
import logging
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import yaml

from cmn.dependencies import set_aside_foundations, set_aside_foundations_of
from cmn.pytest_support import case_identifier
from ingestion.cases import build_case_id

from tests.cases import suite_support
from tests.cases.graded_support import quarantined_cases

logger = logging.getLogger(__name__)

# THE QUESTIONS THIS SESSION RAISED, one per dependent that passed while a
# foundation it rests on is quarantined. Module level because the hook noting
# them and the hook printing them are free functions (section 4.14.2).
_QUESTIONS: list[str] = []


def quarantine_deselection(
    items: list[Any],
    pairs: Mapping[str, tuple[str, str]],
    quarantined: frozenset[str],
) -> tuple[list[Any], list[Any]]:
    """Split the items into those kept and those whose corpus case is quarantined.

    Args:
        items (list): The collected items, each read for ``originalname`` or
            ``name``.
        pairs (Mapping): Case name to the task and rule it dispatches, as
            ``suite_support.case_rules_from_suite`` returns it.
        quarantined (frozenset[str]): The quarantined corpus case identifiers.

    Returns:
        tuple: The items kept and the items dropped, each in collection order.
    """
    kept: list[Any] = []
    dropped: list[Any] = []
    for item in items:
        name = str(getattr(item, "originalname", None) or getattr(item, "name", ""))
        pair = pairs.get(name)
        if pair is not None and build_case_id(*pair) in quarantined:
            dropped.append(item)
        else:
            kept.append(item)
    return kept, dropped


def write_quarantine_file(
    config_dir: Path, engine: str, entries: list[dict[str, Any]]
) -> Path:
    """Write ``quarantine/<engine>.yaml`` under a config directory, for a case to read.

    Args:
        config_dir (Path): The config directory to write under.
        engine (str): The engine the file is for.
        entries (list): The entries, as the file holds them.

    Returns:
        Path: The file written.
    """
    target = config_dir / "quarantine" / f"{engine}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump({"quarantine": entries}, sort_keys=False),
        encoding="utf-8", newline="\n",
    )
    return target


def file_entry(
    case_id: str, quarantined_on: date, observed_model: str, **fields: object
) -> dict[str, object]:
    """Return one quarantine file entry carrying a ticket.

    Args:
        case_id (str): The composed case identifier.
        quarantined_on (date): The date the entry was last stamped.
        observed_model (str): The model it was observed against.
        **fields (object): Fields overriding the defaults.

    Returns:
        dict: The entry as the file holds it.
    """
    return {
        "case_id": case_id, "reason": "known failure",
        "quarantined_on": quarantined_on.isoformat(),
        "observed_model": observed_model, "ticket": "MQC-41", **fields,
    }


def dropped_names(pairs: Mapping[str, tuple[str, str]], held: frozenset[str]) -> list[str]:
    """Return the case names collection drops for a held set, one item per name.

    Args:
        pairs (Mapping): Case name to the task and rule it dispatches.
        held (frozenset[str]): The case identifiers held out.

    Returns:
        list[str]: The names dropped, in the mapping's order.
    """
    items = [SimpleNamespace(name=name) for name in pairs]
    _, dropped = quarantine_deselection(items, pairs, held)
    return [item.name for item in dropped]


def held_case_numbers(
    pairs: Mapping[str, tuple[str, str]], held: frozenset[str]
) -> frozenset[str]:
    """Return the case number of every suite case whose corpus case is held out.

    Args:
        pairs (Mapping): Case name to the task and rule it dispatches, over the
            whole suite rather than this band's collection.
        held (frozenset[str]): The corpus case identifiers in force.

    Returns:
        frozenset[str]: The six-digit case numbers, the form a ``depends_on``
        declaration names.
    """
    numbers: set[str] = set()
    for name, pair in pairs.items():
        number = case_identifier(name)
        if number is not None and build_case_id(*pair) in held:
            numbers.add(number)
    return frozenset(numbers)


def note_foundation_question(item: Any, report: Any) -> None:
    """Record a question about each set-aside foundation a passing case rests on.

    Only the call phase of a pass counts: a dependent that held while its
    foundation is quarantined is evidence about the foundation.

    Args:
        item (Any): The case that ran.
        report (Any): The phase report pytest produced.

    Returns:
        None
    """
    if getattr(report, "when", "") != "call" or not getattr(report, "passed", False):
        return
    for foundation in set_aside_foundations_of(item):
        _QUESTIONS.append(
            f"Investigate the foundation: {getattr(item, 'name', '')} passed while "
            f"its foundation {foundation} is quarantined"
        )


def foundation_questions() -> list[str]:
    """Return every question raised this session about a quarantined foundation.

    Returns:
        list[str]: One line per dependent that passed on a set-aside foundation.
    """
    return list(_QUESTIONS)


def clear_foundation_questions() -> None:
    """Forget the questions raised, which a case on them needs between runs.

    Returns:
        None
    """
    _QUESTIONS.clear()


def declared_dependents(folder: Path) -> dict[str, list[str]]:
    """Return each foundation's dependents, as the case modules declare them.

    Read from the parsed ``depends_on`` decorators, never the source text, so a
    docstring quoting one is not a declaration.

    Args:
        folder (Path): The directory holding the case modules.

    Returns:
        dict[str, list[str]]: Foundation case number to the names of the cases
        resting on it, in source order.
    """
    graph: dict[str, list[str]] = {}
    for source in sorted(folder.glob("mqc_*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for deco in node.decorator_list:
                if (
                    isinstance(deco, ast.Call)
                    and getattr(deco.func, "attr", "") == "depends_on"
                ):
                    for argument in deco.args:
                        graph.setdefault(str(getattr(argument, "value", "")), []).append(
                            node.name
                        )
    return graph


def dependent_item(name: str, *foundations: str) -> SimpleNamespace:
    """Return a stand-in for a collected case resting on the named foundations.

    Args:
        name (str): The case name.
        *foundations (str): The case numbers it depends on.

    Returns:
        SimpleNamespace: An object answering ``name`` and ``iter_markers`` as
        the cascade reads them.
    """
    marker = SimpleNamespace(args=foundations)

    def iter_markers(name: str = "") -> list[SimpleNamespace]:
        """Return the ``depends_on`` marker, and nothing for any other name.

        Args:
            name (str): The marker asked for.

        Returns:
            list: The marker, or nothing.
        """
        return [marker] if name == "depends_on" and foundations else []

    return SimpleNamespace(name=name, iter_markers=iter_markers)


def called_names(source: Path) -> set[str]:
    """Return every name a module calls or imports.

    Args:
        source (Path): The module.

    Returns:
        set[str]: The called function and attribute names, and the imported names.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {node.name for node in ast.walk(tree) if isinstance(node, ast.alias)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            names.add(str(getattr(node.func, "id", None) or getattr(node.func, "attr", "")))
    return names


def top_level_calls(source: Path, function: str) -> set[str]:
    """Return the names called by a function's statements outside any branch or loop.

    Args:
        source (Path): The module defining the function.
        function (str): The function's name.

    Returns:
        set[str]: The called names, empty where the function is not defined.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.FunctionDef) and node.name == function):
            continue
        for statement in node.body:
            if isinstance(statement, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                continue
            for inner in ast.walk(statement):
                if isinstance(inner, ast.Call):
                    names.add(
                        str(getattr(inner.func, "id", None) or getattr(inner.func, "attr", ""))
                    )
    return names


def deselect_quarantined_cases(config: Any, items: list[Any], root: Path) -> int:
    """Drop every collected case the run's engine has quarantined.

    Reads the suite only where the engine has a quarantined case, so a run
    with none pays nothing for it.

    Args:
        config (Any): pytest's configuration, read for ``--engine`` and
            carrying the deselection hook.
        items (list): The collected items, changed in place.
        root (Path): This repository's root.

    Returns:
        int: How many cases were dropped.
    """
    quarantined = quarantined_cases(config)
    if not quarantined:
        return 0
    pairs = suite_support.case_rules_from_suite(root)
    # EVERY HELD CASE IS SET ASIDE, collected in this band or not: a later
    # band's dependent rests on a foundation an earlier band dropped, and its
    # dependents run and count rather than refusing the run (section 4.14.2).
    set_aside_foundations(held_case_numbers(pairs, quarantined))
    kept, dropped = quarantine_deselection(items, pairs, quarantined)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept
        logger.info(
            "Quarantine: %d case(s) deselected, each with a ticket against it: %s",
            len(dropped), ", ".join(str(getattr(item, "name", "")) for item in dropped),
        )
    return len(dropped)
