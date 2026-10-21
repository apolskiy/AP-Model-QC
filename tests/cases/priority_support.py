# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Support code reading a graded case's priority from each place that states it.

Created: 2026-10-15
Last updated: 2026-10-21

This file contains ``inventoried_priorities``, which reads each graded case's level and
qualifying condition from its inventory row in the test plan, and ``marked_priorities``,
which reads the level each graded case's ``priority`` marker applies.

**Only ``mqc_uni_priority_agreement.py`` imports it**, in the ``unit`` precondition
gate, which compares both with the priority in the case's rule. It is not collected
itself, as its name carries no ``mqc_`` prefix.

Specified in ``docs/testing/model_evaluation_test_plan.md`` section 8.1.2.
"""

import ast
import re
from pathlib import Path
from typing import Final, Optional

ROOT: Final[Path] = Path(__file__).resolve().parents[2]
PLAN: Final[Path] = ROOT / "docs" / "testing" / "model_evaluation_test_plan.md"

# THE CONDITION COLUMN IS WHAT MAKES A ROW AN INVENTORY ROW. Section 9.10.2
# has a table of the same shape whose third column is a vector, and reading
# it as an inventory overwrote the rows it shares identifiers with.
_ROW: Final[re.Pattern[str]] = re.compile(
    r"^\| `(\d{6})` \| P(\d) \| `(P\d_\w+)` \|", re.MULTILINE
)
_CASE: Final[re.Pattern[str]] = re.compile(r"^MQC_[A-Z]+_(?:EVAL|TOOL|SEC)_(\d{6})_")


def inventoried_priorities() -> dict[str, tuple[int, str]]:
    """Return each graded case's inventoried priority and condition.

    Returns:
        dict: Six-digit identifier to its level and condition, from the test
        plan's inventory rows.
    """
    text = PLAN.read_text(encoding="utf-8")
    return {match.group(1): (int(match.group(2)), match.group(3)) for match in _ROW.finditer(text)}


def _marker(decorators: list[ast.expr]) -> Optional[int]:
    """Return the level a ``priority`` marker applies, if one is among them.

    Args:
        decorators (list): A definition's decorators.

    Returns:
        Optional[int]: The level, or None.
    """
    for node in decorators:
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "priority" and node.args
                and isinstance(node.args[0], ast.Constant)):
            return int(node.args[0].value)
    return None


def marked_priorities() -> dict[str, tuple[str, int]]:
    """Return each graded case's name and the level its marker applies.

    Returns:
        dict: Six-digit identifier to the case's name and level, the method's
        own marker taking precedence over its class's.
    """
    found: dict[str, tuple[str, int]] = {}
    for path in sorted((ROOT / "tests" / "cases").glob("mqc_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
            inherited = _marker(owner.decorator_list)
            for method in (node for node in owner.body if isinstance(node, ast.FunctionDef)):
                match = _CASE.match(method.name)
                level = _marker(method.decorator_list)
                level = inherited if level is None else level
                if match and level is not None:
                    found[match.group(1)] = (method.name, level)
    return found
