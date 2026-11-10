# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Stand-in judges and collection probes for the calibration unit cases.

Created: 2026-11-10
Last updated: 2026-11-10

This file contains :class:`StandInJudge`, which answers a calibration request
with the score a rule gives the exemplar's level and keeps every request it
received; :class:`StoppedJudge`, which raises the error a judge channel raises
once it has stopped answering; ``rubric_exemplars``, which lists the exemplars
of some cases' rubrics; and ``collect_calibration``, which collects the
calibration cases in a separate pytest process under a given selection.

``mqc_uni_calibration.py`` passes the judges to ``calibrate_family`` in place
of a live channel, so its cases call no provider. ``collect_calibration`` runs
``--collect-only``, which collects and calls nothing.

**The judge reads the criteria out of the request**, so a request carrying the
wrong schema produces a ``KeyError`` here instead of a passing case.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parents[2]
_CALIBRATION_MODULE = "tests/cases/mqc_eval_calibration.py"


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
