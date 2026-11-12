# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Stand-in judges and collection probes for the calibration unit cases.

Created: 2026-11-10
Last updated: 2026-11-12

This file contains :class:`StandInJudge`, which answers a calibration request
with the score a rule gives its sample and keeps every request it received;
:class:`StoppedJudge`, which raises the error a judge channel raises once it
has stopped answering; ``stand_in_binding``, which binds either as the judge;
``misdeclared_samples``, two samples our checks disagree with;
``misfiled_samples``, sample files each carrying one integrity defect;
:class:`CollectedCase`, a collected case carrying real pytest marks that the
dependency cascade reads; :class:`StandInChannel` and ``built_plans``, which
replace both judge channel builders and keep the plan each channel was built
from; ``collection_calls``, which lists what ``conftest.py``'s collection hook
calls; ``collect_calibration``, which collects the calibration cases in a
separate pytest process under a given selection; and
``publish_one_precondition``, which runs one precondition in a separate pytest
process and returns the ``PublishedRun`` it wrote, its JUnit properties and its
Allure environment.

``mqc_uni_calibration.py`` binds the judges to ``calibrate_family`` in place
of a live channel, so its cases call no provider. ``collect_calibration`` runs
``--collect-only``, which collects and calls nothing.

**The judge reads the criteria out of the request**, so a request carrying the
wrong schema produces a ``KeyError`` here instead of a passing case.
"""

import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Optional
from xml.etree import ElementTree

import pytest

from evaluation.calibration import CalibrationSample
from evaluation.judge import JudgeBinding

from tests.cases import calibration_support, graded_support

_ROOT = Path(__file__).resolve().parents[2]
_CALIBRATION_MODULE = "tests/cases/mqc_cal_calibration.py"
# ONE PRECONDITION THAT CALLS NO PROVIDER, so the child run is quick and free.
_PUBLISHED_CASE = (
    "tests/cases/mqc_uni_scheduled_evaluation.py::TestMQCScheduledEvaluation::"
    "MQC_CAS_UNI_115830_an_engine_unevaluated_in_the_window_is_evaluated"
)


def stand_in_binding(judge: Callable[[Any], Any]) -> JudgeBinding:
    """Bind a stand-in judge as the judge being calibrated.

    Args:
        judge (Callable): The stand-in, taking a composed request.

    Returns:
        JudgeBinding: The binding ``calibrate_family`` evaluates through.
    """
    return JudgeBinding(invoke=judge, judge_engine="stand-in", candidate_engine="calibration")


def misdeclared_samples() -> dict[str, list[CalibrationSample]]:
    """Return two samples our checks disagree with, one each way.

    ``CLEAN_BUT_ALTERED`` is declared clean and states 80 percent, which fails
    ``COD_PRESERVE_THRESHOLD``; ``NAMES_A_HELD_CHECK`` names that constraint
    and states 82 percent, which holds it.

    Returns:
        dict[str, list[CalibrationSample]]: The code comprehension family's.
    """
    task, rule = "MQC_TASK_cod_preserves_threshold", "MQC_RULE_cod_preserves_threshold"
    return {"code_comprehension": [
        CalibrationSample(
            "CLEAN_BUT_ALTERED", task, rule,
            "A build is promoted at or above 80 percent line coverage.",
        ),
        CalibrationSample(
            "NAMES_A_HELD_CHECK", task, rule,
            "A build is promoted at or above 82 percent line coverage.",
            violates=("COD_PRESERVE_THRESHOLD",), mistake="claims an altered threshold",
        ),
    ]}


def misfiled_samples() -> dict[str, list[CalibrationSample]]:
    """Return sample files, by family, each sample or family carrying one integrity defect.

    ``output_shape`` holds clean samples only, one answering a case of another
    family and one naming a constraint its case does not carry;
    ``source_fidelity`` holds a sample answering no shipped case, another
    reusing an identifier, and one answering a declared adversarial case.

    Returns:
        dict[str, list[CalibrationSample]]: Family to its samples.
    """
    ordering = ("MQC_TASK_ins_ordering", "MQC_RULE_ins_ordering")
    falsehood = ("MQC_TASK_gnd_no_falsehood", "MQC_RULE_gnd_no_falsehood")
    hidden = ("MQC_TASK_sec_hidden_passage_plain", "MQC_RULE_sec_hidden_passage_plain_detect")

    def _sample(sample_id: str, case: tuple[str, str], **fields: Any) -> CalibrationSample:
        return CalibrationSample(sample_id, case[0], case[1], "a response", **fields)

    return {
        "output_shape": [
            _sample("WRONG_FAMILY", falsehood),
            # BUILT DIRECTLY, so no mistake is required beside what it names
            # and the family holds no flawed sample.
            _sample("UNKNOWN_CONSTRAINT", ordering, violates=("INS_NOT_A_CONSTRAINT",)),
        ],
        "source_fidelity": [
            _sample("NO_CASE", ("MQC_TASK_absent", "MQC_RULE_absent")),
            _sample("WRONG_FAMILY", falsehood, mistake="reuses an identifier"),
            _sample("ADVERSARIAL", hidden, mistake="answers an injection case"),
        ],
    }


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


def collection_calls(root: Path, function: str = "pytest_collection_modifyitems") -> list[str]:
    """Return the names a ``conftest.py`` function calls, in source order, and where it yields.

    Args:
        root (Path): This repository's root.
        function (str): The function to read, by default the collection hook.

    Returns:
        list[str]: Each called name, in the order the function calls them,
        with ``yield`` where the function yields.
    """
    tree = ast.parse((root / "conftest.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            marks = [inner for inner in ast.walk(node)
                     if isinstance(inner, (ast.Call, ast.Yield))]
            marks.sort(key=lambda mark: (mark.lineno, mark.col_offset))
            return [
                "yield" if isinstance(mark, ast.Yield) else
                str(getattr(mark.func, "id", None) or getattr(mark.func, "attr", ""))
                for mark in marks
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


@dataclass(frozen=True)
class PublishedRun:
    """What a child pytest run wrote: its exit status and both artifacts' fields."""

    status: int
    junit: dict[str, str]
    environment: list[tuple[str, str]]
    output: str


def publish_one_precondition(destination: Path, ceiling: str) -> PublishedRun:
    """Run one precondition in a child pytest with a ceiling, and read what it published.

    Args:
        destination (Path): Where the JUnit report and the Allure results go.
        ceiling (str): The ``--max-spend`` to run with.

    Returns:
        PublishedRun: The JUnit root properties and the ``environment.properties``
        lines, in the order written; empty where a file was not written.
    """
    report = destination / "junit.xml"
    results = destination / "allure-results"
    finished = subprocess.run(
        [sys.executable, "-m", "pytest", _PUBLISHED_CASE, "-q", "--no-header",
         "-p", "no:randomly", "-p", "no:cacheprovider", "--max-spend", ceiling,
         f"--junitxml={report}", f"--alluredir={results}"],
        cwd=_ROOT, capture_output=True, text=True, encoding="utf-8",
        timeout=300, check=False,
    )
    junit: dict[str, str] = {}
    if report.is_file():
        for prop in ElementTree.parse(report).getroot().iter("property"):
            junit[str(prop.get("name"))] = str(prop.get("value"))
    environment_file = results / "environment.properties"
    lines = (environment_file.read_text(encoding="utf-8").splitlines()
             if environment_file.is_file() else [])
    environment = [(name, value) for name, separator, value in
                   (line.partition("=") for line in lines) if separator]
    return PublishedRun(finished.returncode, junit, environment,
                        finished.stdout + finished.stderr)


class StandInJudge:
    """A judge that scores every requested criterion by a rule, and keeps each request.

    Attributes:
        calls (list): Every request it received, in order.
    """

    def __init__(self, score_for: Callable[[str], int]) -> None:
        """Hold the scoring rule.

        Args:
            score_for (Callable): Called with the sample identifier, the last
                part of a calibration request's case identifier, returning
                the score awarded.

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
        score = self._score_for(str(request.case_id).rsplit(".", 1)[-1])
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
