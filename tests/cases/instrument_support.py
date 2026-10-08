# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""The apparatus the instrument cases assert against, doubles included.

Specified by the harness ``harness_test_taxonomy.md`` section 13.

**Extracted 2026-10-05**, when the case module stood at 939 lines. Two kinds of
thing live here: readers that answer what the designs and the suite declare,
and two configuration doubles the graded and dispatch paths are driven with.
A double is apparatus by definition.

**Public names, deliberately.** A support module is an interface, and a leading
underscore on something another module imports says the opposite of what is
true.

**`_repository_root` is gone rather than moved**, being one of four
byte-identical copies of ``graded_support.repository_root``.
"""

import ast
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

from execution.dispatch import DispatchOutcome
from execution.normalize import NormalizedResponse


def designed_foundations(plan: Path) -> dict[str, set[str]]:
    """Return what each security inventory row says a case presupposes.

    Args:
        plan (Path): The test plan carrying the inventory table.

    Returns:
        dict: Case number to the case numbers its row names.
    """
    designed: dict[str, set[str]] = {}
    for line in plan.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if INVENTORY_ROW.match(row) is None:
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) < 4:
            continue
        number = BACKTICKED_ID.search(cells[0])
        if number is None:
            continue
        designed[number.group(1)] = {
            found.group(1) for found in BACKTICKED_ID.finditer(cells[3])
        }
    return designed


def declared_foundations(folder: Path) -> dict[str, set[str]]:
    """Return what each security case declares through ``depends_on``.

    **From the parsed syntax, never the source text.** A ``depends_on`` inside a
    docstring is prose, and this repository quotes case identifiers constantly.

    Args:
        folder (Path): The directory holding the case modules.

    Returns:
        dict: Case number to the case numbers it rests on.
    """
    declared: dict[str, set[str]] = {}
    for source in sorted(folder.glob("mqc_sec_*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            found = CASE_NUMBER.search(node.name)
            if found is None:
                continue
            declared[found.group(1)] = {
                str(getattr(deco.args[0], "value", ""))
                for deco in node.decorator_list
                if isinstance(deco, ast.Call)
                and getattr(deco.func, "attr", "") == "depends_on"
                and deco.args
            }
    return declared


def named_pairs_in(node: ast.FunctionDef) -> list[tuple[int, str, str]]:
    """Return every task and rule pair one test callable names literally.

    **Scoped to one callable**, where :func:`_named_pairs` reads a whole module.
    `115400` asks which case bound which pair, so the owning callable has to be
    known rather than the file.

    Args:
        node (ast.FunctionDef): The test callable.

    Returns:
        list: Line number, task id and rule id for each pair found.
    """
    found: list[tuple[int, str, str]] = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        name = getattr(inner.func, "id", None) or getattr(inner.func, "attr", None)
        if name not in {"observe", "observe_repeatedly", "case_for"}:
            continue
        pair = [
            argument.value
            for argument in inner.args
            if isinstance(argument, ast.Constant)
            and isinstance(argument.value, str)
            and argument.value.startswith("MQC_")
        ]
        if len(pair) >= 2:
            found.append((inner.lineno, pair[0], pair[1]))
    return found


def stripped(text: str) -> str:
    """Return the text with trailing whitespace removed from every line.

    Args:
        text (str): The recorded response.

    Returns:
        str: The same text, each line right-stripped.
    """
    return "\n".join(line.rstrip() for line in text.split("\n"))


def recorded_text(fixture: Path) -> str:
    """Return the longest candidate text a recorded fixture carries.

    **The longest rather than the first**, because a provider reply nests text
    under several keys and only one of them is the answer.

    Args:
        fixture (Path): The recorded candidate fixture.

    Returns:
        str: The candidate output, or empty when the fixture carries none.
    """
    found: list[str] = []
    stack: list[Any] = [json.loads(fixture.read_text(encoding="utf-8"))]
    while stack:
        payload = stack.pop()
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key == "text" and isinstance(value, str):
                    found.append(value)
                else:
                    stack.append(value)
        elif isinstance(payload, list):
            stack.extend(payload)
    return max(found, key=len) if found else ""


class FakeGradedConfig:
    """Enough of pytest's config for the graded helpers to read a run.

    Built here rather than through a pytest run because the question is what
    the helpers conclude from a given command line, which needs no session.
    """

    def __init__(self, judge_engine: str, observations: int = 0) -> None:
        """Hold the flags these two cases vary, with the rest at their defaults.

        Args:
            judge_engine (str): What ``--judge-engine`` was given.
            observations (int): What ``--observations`` was given, zero for
                unnamed.

        Returns:
            None
        """
        self._values: dict[str, Any] = {
            "--engine": "gemini",
            "--mode": "replay",
            "--judge-mode": "",
            "--judge-engine": judge_engine,
            "--observations": observations,
            "--keep-connection": False,
            "--fill-gaps": False,
            "--max-spend": 0.0,
        }
        self.option = SimpleNamespace()

    def getoption(self, name: str, default: Any = None) -> Any:
        """Return a parsed value, as pytest would.

        Args:
            name (str): The option's flag or destination name.
            default (Any): What to return when it is unset.

        Returns:
            Any: The value.
        """
        return self._values.get(name, default)


def dispatch_outcome(model: str, mode: str = "live") -> Any:
    """Build one dispatch outcome reporting a resolved model.

    Args:
        model (str): What the response reported serving.
        mode (str): ``live`` or ``replay``.

    Returns:
        Any: The :class:`DispatchOutcome`.
    """
    return DispatchOutcome(
        case_id="MQC_TASK_a::MQC_RULE_r", engine="gemini", mode=mode,
        duration_ms=12, duration_kind="measured", attempts=1,
        rate_limit_encounters=0,
        response=NormalizedResponse(
            case_id="MQC_TASK_a::MQC_RULE_r", engine="gemini", mode=mode,
            requested_model=model, resolved_model=model, text="answer",
            output_tokens=7, duration_ms=12, finish_reason="stop",
            raw_reference="",
        ),
    )


class FakeDispatchConfig:
    """The flags ``dispatch_session`` reads, with the rest at their defaults."""

    def __init__(self, engine: str = "gemini", ceiling: float = 0.0) -> None:
        """Hold the two values that define a session.

        Args:
            engine (str): Which engine paces the run.
            ceiling (float): The spend ceiling, zero for none.

        Returns:
            None
        """
        self._values: dict[str, Any] = {
            "--engine": engine,
            "--mode": "replay",
            "--max-spend": ceiling,
            "--keep-connection": False,
            "--fill-gaps": False,
        }

    def getoption(self, name: str, default: Any = None) -> Any:
        """Return a parsed value, as pytest would.

        Args:
            name (str): The option's flag name.
            default (Any): What to return when it is unset.

        Returns:
            Any: The value.
        """
        return self._values.get(name, default)

# A security inventory row, whose fourth cell names the cases it presupposes.
# THE SECURITY BLOCK, which the six-digit scheme moved from 5xxxx to 15xxxx:
# domain 1, layer 5. This encoded the block prefix rather than a digit count,
# so the widening sweep did not reach it and the row stopped matching at all.
INVENTORY_ROW: Final[re.Pattern] = re.compile(r"^\|\s*`(15\d{4})`\s*\|")


BACKTICKED_ID: Final[re.Pattern] = re.compile(r"`(\d{6})`")


CASE_NUMBER: Final[re.Pattern] = re.compile(r"_(\d{6})_")
