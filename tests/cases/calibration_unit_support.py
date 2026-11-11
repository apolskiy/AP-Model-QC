# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Stand-in judges and collection probes for the calibration unit cases.

Created: 2026-11-10
Last updated: 2026-11-11

This file contains :class:`StandInJudge`, which answers a calibration request
with the score a rule gives the exemplar's level and keeps every request it
received; :class:`StoppedJudge`, which raises the error a judge channel raises
once it has stopped answering; :class:`CollectedCase`, a collected case
carrying real pytest marks that the dependency cascade reads;
:class:`StandInChannel` and ``built_plans``, which replace both judge channel
builders and keep the plan each channel was built from;
``collection_calls``, which lists what ``conftest.py``'s collection hook calls;
``rubric_exemplars``, which lists the exemplars of some cases' rubrics; and
``collect_calibration``, which collects the calibration cases in a separate
pytest process under a given selection.

``mqc_uni_calibration.py`` passes the judges to ``calibrate_family`` in place
of a live channel, so its cases call no provider. ``collect_calibration`` runs
``--collect-only``, which collects and calls nothing.

**The judge reads the criteria out of the request**, so a request carrying the
wrong schema produces a ``KeyError`` here instead of a passing case.
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

import pytest

from tests.cases import calibration_support, graded_support

_ROOT = Path(__file__).resolve().parents[2]
_CALIBRATION_MODULE = "tests/cases/mqc_cal_calibration.py"


def rubric_exemplars(cases: list[Any]) -> list[tuple[str, str, int]]:
    """Return every exemplar the cases' rubrics carry, by case, criterion and level.

    Args:
        cases (list): Shipped evaluation cases.

    Returns:
        list[tuple[str, str, int]]: One entry per exemplar.
    """
    return [
        (case.case_id, criterion.criterion_id, level)
        for case in cases
        for criterion in case.golden_rules.rubric.criteria
        for level, anchor in sorted(criterion.anchors.items())
        if anchor.exemplar is not None
    ]


def built_plans(monkeypatch: Any) -> list[Any]:
    """Replace both judge channel builders with one that keeps the plan it was handed.

    Args:
        monkeypatch (Any): pytest's patcher, which restores both builders.

    Returns:
        list[Any]: Every plan a channel is built from, in order.
    """
    plans: list[Any] = []

    def _builder(roster: Any, engine: Any, **options: Any) -> Any:
        del roster
        plans.append(options["plan"])
        return StandInChannel(engine)

    monkeypatch.setattr(graded_support, "judge_channel_from_roster", _builder)
    monkeypatch.setattr(calibration_support, "judge_channel_from_roster", _builder)
    return plans


def collection_calls(root: Path) -> list[str]:
    """Return the names ``conftest.py``'s collection hook calls, in source order.

    Args:
        root (Path): This repository's root.

    Returns:
        list[str]: Each called name, in the order the hook calls them.
    """
    tree = ast.parse((root / "conftest.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "pytest_collection_modifyitems":
            calls = [inner for inner in ast.walk(node) if isinstance(inner, ast.Call)]
            calls.sort(key=lambda call: (call.lineno, call.col_offset))
            return [
                str(getattr(call.func, "id", None) or getattr(call.func, "attr", ""))
                for call in calls
            ]
    return []


def collect_calibration(markexpr: str, *options: str) -> tuple[int, str]:
    """Collect the calibration module in a separate pytest process, calling nothing.

    Args:
        markexpr (str): The marker expression the run selects by.
        *options (str): Further flags, such as the mode and the judge mode.

    Returns:
        tuple[int, str]: The exit status and the combined output.
    """
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", _CALIBRATION_MODULE, "--collect-only", "-q",
         "-p", "no:randomly", "-m", markexpr, *options],
        cwd=_ROOT, capture_output=True, text=True, encoding="utf-8",
        timeout=300, check=False,
    )
    return finished.returncode, finished.stdout + finished.stderr


class StandInJudge:
    """A judge that scores every requested criterion by a rule, and keeps each request.

    Attributes:
        calls (list): Every request it received, in order.
    """

    def __init__(self, score_for: Callable[[int], int]) -> None:
        """Hold the scoring rule.

        Args:
            score_for (Callable): Called with the request's observation index,
                which a calibration request sets to the exemplar's level,
                returning the score awarded.

        Returns:
            None
        """
        self._score_for = score_for
        self.calls: list[Any] = []

    def __call__(self, request: Any) -> dict[str, Any]:
        """Score one request.

        Args:
            request (Any): The composed judge request.

        Returns:
            dict: A reply in the shape the reply schema requires.
        """
        self.calls.append(request)
        score = self._score_for(request.observation_index)
        return {"scores": {
            criterion_id: {"score": score, "rationale": "stand-in"}
            for criterion_id in request.reply_schema["properties"]["scores"]["required"]
        }}


class CollectedCase:
    """A collected case carrying pytest marks, which the dependency cascade can add to and read.

    Attributes:
        name (str): The callable's name, carrying its identifier.
        originalname (str): The same name, as pytest gives an unparametrized case.
        nodeid (str): A node identifier carrying the name.
        config (None): No invocation, so no run opens an inquest.
    """

    def __init__(self, name: str, *markers: str) -> None:
        """Hold the case and the marks it was declared with.

        Args:
            name (str): The callable's name.
            *markers (str): The marker names it is declared with.

        Returns:
            None
        """
        self.name = name
        self.originalname = name
        self.nodeid = f"tests/cases/mqc_x.py::TestMQCX::{name}"
        self.config = None
        self._marks: list[Any] = [getattr(pytest.mark, marker).mark for marker in markers]

    def add_marker(self, marker: Any) -> None:
        """Add a mark, as pytest's item does.

        Args:
            marker (Any): A mark decorator.

        Returns:
            None
        """
        self._marks.append(marker.mark)

    def iter_markers(self, name: Optional[str] = None) -> Iterator[Any]:
        """Yield the marks carrying a name, or every mark.

        Args:
            name (Optional[str]): The marker name, or None for all.

        Yields:
            Any: Each matching mark, in the order added.
        """
        for mark in self._marks:
            if name is None or mark.name == name:
                yield mark

    def get_closest_marker(self, name: str) -> Any:
        """Return the first mark carrying a name.

        Args:
            name (str): The marker name.

        Returns:
            Any: The mark, or None.
        """
        return next(self.iter_markers(name), None)


class StandInChannel:
    """A judge channel that is built and never asked anything.

    Attributes:
        engine (str): The judge named.
        stopped (None): Never stopped.
    """

    def __init__(self, engine: Any) -> None:
        """Hold the judge's name.

        Args:
            engine (Any): The judge engine the builder was given.

        Returns:
            None
        """
        self.engine = str(engine or "")
        self.stopped = None

    def invoke(self, request: Any) -> Any:
        """Refuse a request, which no case here sends.

        Args:
            request (Any): The composed judge request.

        Returns:
            Any: Never returns.

        Raises:
            LookupError: Always.
        """
        raise LookupError(f"the stand-in channel was asked {request!r}")


class StoppedJudge:
    """A judge that raises what a stopped judge channel raises.

    Attributes:
        calls (list): Every request it received, in order.
    """

    def __init__(self, message: str) -> None:
        """Hold the message to raise.

        Args:
            message (str): The error text, led by its code.

        Returns:
            None
        """
        self._message = message
        self.calls: list[Any] = []

    def __call__(self, request: Any) -> dict[str, Any]:
        """Refuse one request.

        Args:
            request (Any): The composed judge request.

        Returns:
            dict: Never.

        Raises:
            ValueError: Always, carrying the held message.
        """
        self.calls.append(request)
        raise ValueError(self._message)
