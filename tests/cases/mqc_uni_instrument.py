# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the instrument measures the claim each case name makes.

Covers ``MQC_CAS_UNI_10461``, ``10462`` and ``10463``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.1, and
``MQC_CAS_UNI_10470`` and ``10471``, inventoried in ``consumer_ci.md``
section 4 and designed in sections 4.13 and 4.13.1.

**Three failures of one kind, found on one day.** Four cases bound one task and
rule pair and asserted the conjunction of its four assertions, so a red named
the wrong claim. An assertion was defeated by two trailing spaces and reported a
compliant answer as instruction drift. And an adapter withheld content without
recording why, so a provider refusal read as a model failure. Each would have
been filed against a vendor.

**Extracted from ``mqc_uni_corpus.py`` on 2026-10-01**, which crossed the
thousand-line ceiling. The subject is not the corpus: these ask whether a result
means what it says, which is a property of the measuring apparatus rather than
of the data it measures.

A failure here is our defect, so the module carries no priority marker, per the
harness ``framework-rules.md`` section 3.3.
"""

import ast
import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

import allure
import pytest

from cmn.observations import further_observations
from cmn.config import load_quarantine_for
from cmn.vectors import is_registered_vector, match_vectors
from evaluation.assertions import run_assertions
from ingestion.schemas import GoldenRuleSet, TaskDataSet
from execution.dispatch import DispatchOutcome, DispatchSession
from execution.normalize import NormalizedResponse
from tools.quarantine import main as quarantine_tool, parse_as_of
from tests.cases.graded_support import (
    dispatch_session,
    judge_binding,
    observation_count,
    shipped_corpus,
)

pytestmark = pytest.mark.unit


# A SHIPPED CASE WITH RECORDED FIXTURES, so the tool's case replays rather than
# dispatching. Named here because what it relies on is that the pair exists and
# replays green, not anything about its subject.
_REPLAYABLE_CASE = "MQC_TASK_amb_unambiguous_request::MQC_RULE_amb_unambiguous_request"

# THIS REPOSITORY HAS TWO INVENTORY SHAPES. The precondition table carries an
# identifier, a category and a behaviour; the graded tables carry a priority and
# a condition between them. A row matching neither is a citation.
_PRECONDITION_ROW: Final[re.Pattern] = re.compile(
    r"^\|\s*`(\d{5,6})`\s*\|\s*[PNB]\s*\|\s*`[a-z0-9_]+`"
)
_GRADED_ROW: Final[re.Pattern] = re.compile(
    r"^\|\s*`(\d{5,6})`\s*\|\s*P\d\s*\|\s*`[A-Z0-9_]+`\s*\|\s*[PNB]\s*\|\s*`[a-z0-9_]+`"
)


# A security inventory row, whose fourth cell names the cases it presupposes.
_INVENTORY_ROW: Final[re.Pattern] = re.compile(r"^\|\s*`(5\d{4})`\s*\|")
_BACKTICKED_ID: Final[re.Pattern] = re.compile(r"`(\d{5,6})`")
_CASE_NUMBER: Final[re.Pattern] = re.compile(r"_(\d{5,6})_")



def _repository_root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``data/``.
    """
    return Path(__file__).resolve().parents[2]


def _designed_foundations(plan: Path) -> dict[str, set[str]]:
    """Return what each security inventory row says a case presupposes.

    Args:
        plan (Path): The test plan carrying the inventory table.

    Returns:
        dict: Case number to the case numbers its row names.
    """
    designed: dict[str, set[str]] = {}
    for line in plan.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if _INVENTORY_ROW.match(stripped) is None:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 4:
            continue
        number = _BACKTICKED_ID.search(cells[0])
        if number is None:
            continue
        designed[number.group(1)] = {
            found.group(1) for found in _BACKTICKED_ID.finditer(cells[3])
        }
    return designed


def _declared_foundations(folder: Path) -> dict[str, set[str]]:
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
            found = _CASE_NUMBER.search(node.name)
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


@pytest.fixture(name="corpus")
def fixture_corpus() -> tuple[list[TaskDataSet], list[GoldenRuleSet]]:
    """Load every shipped task and rule file.

    **Through the one loader in `graded_support`**, which three callers each had
    a copy of until 2026-10-01. Copies in a list of lists of the same files are
    the drift a single implementation exists to prevent.

    Returns:
        tuple: Every task and every rule set, across all corpus files.
    """
    tasks, rules = shipped_corpus()
    return list(tasks), list(rules)


def _named_pairs_in(node: ast.FunctionDef) -> list[tuple[int, str, str]]:
    """Return every task and rule pair one test callable names literally.

    **Scoped to one callable**, where :func:`_named_pairs` reads a whole module.
    `10461` asks which case bound which pair, so the owning callable has to be
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

def _stripped(text: str) -> str:
    """Return the text with trailing whitespace removed from every line.

    Args:
        text (str): The recorded response.

    Returns:
        str: The same text, each line right-stripped.
    """
    return "\n".join(line.rstrip() for line in text.split("\n"))

def _recorded_text(fixture: Path) -> str:
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


@allure.epic("AP-Model-QC")
@allure.feature("Corpus")
class TestMQCCasesMeasureTheirOwnClaim:
    """A red has to name the claim that failed.

    All three were written on 2026-10-01 from one triage. `30003` through
    `30006` bound one task and one rule and asserted the conjunction of its four
    assertions, and one of those assertions was defeated by trailing whitespace.
    **Four cases went red and one behaviour was wrong, and that behaviour was
    the model complying.** Test plan sections 9.3.1 and 9.3.2.
    """

    @allure.story("Distinct pairs")
    def MQC_CAS_UNI_10461_a_task_and_rule_pair_bound_by_two_graded_cases_is_reported(
        self,
    ) -> None:
        """No two graded cases bind the same task and rule pair.

        Reads the pair each graded case names, from parsed syntax, and reports
        any pair more than one case binds. Assertions are conjunctive, so cases
        sharing a pair fail together and a red names the conjunction rather than
        the claim the case is about.

        Design: ``model_evaluation_test_plan.md`` section 9.3.1.

        Returns:
            None
        """
        root = _repository_root()
        bound: dict[tuple[str, str], list[str]] = {}
        for pattern in ("mqc_eval_*.py", "mqc_tool_*.py", "mqc_sec_*.py"):
            for source in sorted((root / "tests" / "cases").glob(pattern)):
                tree = ast.parse(
                    source.read_text(encoding="utf-8"), filename=str(source)
                )
                for node in ast.walk(tree):
                    if not isinstance(node, ast.FunctionDef):
                        continue
                    if not node.name.startswith("MQC_"):
                        continue
                    for _, task_id, rule_id in _named_pairs_in(node):
                        bound.setdefault((task_id, rule_id), []).append(node.name)

        assert bound, "no graded case named a pair, so nothing was read"

        shared = {
            pair: sorted(set(names))
            for pair, names in bound.items()
            if len(set(names)) > 1
        }

        assert not shared, (
            f"{len(shared)} task and rule pair(s) are bound by more than one "
            f"graded case, so a red names the conjunction rather than the "
            f"claim: {sorted(shared.items())[:3]}"
        )

    @allure.story("Whitespace insensitivity")
    def MQC_CAS_UNI_10462_an_assertion_sensitive_to_trailing_whitespace_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """No assertion changes its verdict when trailing whitespace is stripped.

        Runs every recorded response through the shipped assertion runner twice,
        as recorded and with each line right-stripped, and reports any assertion
        whose result moves. Only responses actually carrying trailing whitespace
        are examined.

        Over recorded responses rather than synthetic text, so the input is what
        a model wrote.

        Design: ``model_evaluation_test_plan.md`` section 9.3.2.

        Args:
            corpus (tuple): The shipped tasks and rules.

        Returns:
            None
        """
        _, rules = corpus
        by_id = {rule.rule_id: rule for rule in rules}
        root = _repository_root() / "tests" / "fixtures" / "replay"

        moved: list[str] = []
        examined = 0
        for fixture in sorted(root.rglob("*.json")):
            parts = fixture.parts
            if "judgements" in parts or len(parts) < 4:
                continue
            rule = by_id.get(parts[-2])
            if rule is None or not rule.assertions:
                continue
            body = _recorded_text(fixture)
            if not body or body == _stripped(body):
                continue
            examined += 1
            before = run_assertions(rule.assertions, body)
            after = run_assertions(rule.assertions, _stripped(body))
            for first, second in zip(before, after):
                if first.passed != second.passed:
                    moved.append(
                        f"{rule.rule_id}::{first.assertion_id} on "
                        f"{parts[-3]}/{fixture.stem} "
                        f"({'passes' if second.passed else 'fails'} once "
                        f"trailing whitespace is stripped)"
                    )

        assert examined, "no recorded response carried trailing whitespace to test"

        assert not moved, (
            f"{len(moved)} assertion verdict(s) depend on trailing whitespace, "
            f"which is formatting and not a claim any requirement makes: "
            f"{moved[:4]}"
        )
    @allure.story("Refusals")
    def MQC_CAS_UNI_10463_a_recorded_refusal_without_a_stated_reason_is_reported(
        self,
    ) -> None:
        """Every recorded response that withheld content states a reason.

        Reads each recorded candidate fixture and reports any whose
        ``finish_reason`` is ``content_filter`` while ``block_reason`` is empty.
        Section 9.12 passes a case the provider refused and reads
        ``block_reason``, so a refusal recorded without one is counted as a
        model failure.

        Indifferent to which adapter wrote the fixture.

        Design: harness ``tier2_execution.md`` section 4.3.1.

        Returns:
            None
        """
        root = _repository_root() / "tests" / "fixtures" / "replay"
        mute: list[str] = []
        examined = 0
        for fixture in sorted(root.rglob("*.json")):
            if "judgements" in fixture.parts:
                continue
            payload = json.loads(fixture.read_text(encoding="utf-8")).get("response")
            if not isinstance(payload, dict):
                continue
            examined += 1
            if str(payload.get("finish_reason") or "") != "content_filter":
                continue
            if not str(payload.get("block_reason") or "").strip():
                parts = fixture.parts
                mute.append(f"{parts[-4]}/{parts[-3]}/{fixture.stem}")

        assert examined, "no recorded candidate fixture was read"

        assert not mute, (
            f"{len(mute)} recorded response(s) withheld content and stated no "
            f"reason, so a provider refusal reads as a model failure: {mute[:4]}"
        )

    @allure.story("Declared foundations")
    def MQC_CAS_UNI_10464_a_declared_foundation_the_design_does_not_state_is_reported(
        self,
    ) -> None:
        """Each security case's foundations match the ones its design states.

        Parses the ``Presupposes`` column of the security inventory and the
        ``depends_on`` decorators, and reports disagreement in either
        direction: a declared foundation no row lists, and a listed foundation
        the code does not declare.

        Read from parsed syntax, so a ``depends_on`` quoted in prose is not
        counted.

        Design: ``model_evaluation_test_plan.md`` section 9.10.2.3.

        Returns:
            None
        """
        root = _repository_root()
        designed = _designed_foundations(
            root / "docs" / "testing" / "model_evaluation_test_plan.md"
        )
        declared = _declared_foundations(root / "tests" / "cases")

        assert designed and declared, "one of the two artefacts was not read"

        unapproved: list[str] = []
        unimplemented: list[str] = []
        for number, bases in sorted(declared.items()):
            stated = designed.get(number)
            if stated is None:
                if bases:
                    unapproved.append(
                        f"{number} declares {sorted(bases)}, no design row"
                    )
                continue
            for base in sorted(bases - stated):
                unapproved.append(f"{number} declares {base}, the design does not")
            for base in sorted(stated - bases):
                unimplemented.append(f"{number} should rest on {base} and does not")

        assert not unapproved, (
            f"{len(unapproved)} declared foundation(s) no design row states, so "
            f"a failure suppresses a measurement nothing approved: {unapproved}"
        )
        assert not unimplemented, (
            f"{len(unimplemented)} designed foundation(s) the code does not "
            f"declare, so a case runs without its premise: {unimplemented}"
        )

    @allure.story("Declared vectors")
    def MQC_CAS_UNI_10465_an_undeclared_or_unregistered_vector_is_reported(
        self, corpus: tuple[list[TaskDataSet], list[GoldenRuleSet]]
    ) -> None:
        """A declared vector is registered, and a matched one is declared.

        Three directions over the security rules: every key of ``vectors`` is a
        registered vector, ``primary`` names one the rule declares as carried,
        and every vector the payload matches is declared.

        The reverse of the third is not asserted. Some payloads match no vector
        at all, which section 9.10.3 records as a weaker fixture rather than an
        error.

        Design: ``model_evaluation_test_plan.md`` section 9.10.3.1.

        Args:
            corpus (tuple): The shipped tasks and rules.

        Returns:
            None
        """
        tasks, rules = corpus
        by_id = {task.task_id: task for task in tasks}

        problems: dict[str, list[str]] = {
            "unregistered": [], "stray_primary": [], "undeclared": [],
        }
        examined = 0

        for rule in rules:
            declared = getattr(rule, "vectors", None)
            if not isinstance(declared, dict) or not declared:
                continue
            examined += 1
            named = {name for name, state in declared.items() if state}

            for name in sorted(declared):
                if not is_registered_vector(name):
                    problems["unregistered"].append(f"{rule.rule_id} declares {name!r}")

            primary = getattr(rule, "primary", None)
            if primary and primary not in named:
                problems["stray_primary"].append(
                    f"{rule.rule_id} is about {primary!r}, which it does not declare"
                )

            # THE THIRD DIRECTION IS SECURITY ONLY, because the field is.
            # Two benign tool payloads match `task_substitution`, which is the
            # screen being generous rather than a declaration being wrong, and
            # the same class as `score_manipulation` firing on the words
            # "Mandatory Match Score". Reporting it here would make a screen
            # false positive read as a corpus defect.
            task = by_id.get(rule.rule_id.replace("MQC_RULE_", "MQC_TASK_"))
            if task is None or not rule.rule_id.startswith("MQC_RULE_sec_"):
                continue
            for found in match_vectors(json.dumps(task, default=str)):
                if found.vector not in named:
                    problems["undeclared"].append(
                        f"{rule.rule_id} payload matches {found.vector!r} undeclared"
                    )

        assert examined, "no rule declared vectors, so nothing was checked"

        assert not problems["unregistered"], (
            f"{len(problems["unregistered"])} declared vector(s) no registry knows, so a "
            f"typo reads as coverage: {sorted(set(problems["unregistered"]))[:4]}"
        )
        assert not problems["stray_primary"], (
            f"{len(problems["stray_primary"])} rule(s) name a primary outside their declared "
            f"set: {sorted(set(problems["stray_primary"]))[:4]}"
        )
        assert not problems["undeclared"], (
            f"{len(problems["undeclared"])} payload vector(s) a rule does not declare, which "
            f"is the incidental match that let two families look screened: "
            f"{sorted(set(problems["undeclared"]))[:4]}"
        )

    @allure.story("Inventory")
    def MQC_CAS_UNI_10468_an_inventory_row_without_an_implementation_is_reported(
        self,
    ) -> None:
        """Every inventory row in this repository names a case the suite defines.

        Reads both row shapes: the precondition inventory carries an identifier,
        a category and a behaviour, and the graded inventories carry a priority
        and a condition between them. A row matching neither is a citation and
        is not counted.

        Reported rather than gated: an unimplemented row is the normal state
        while a family is authored, and the design comes first here.

        Design: harness ``cmn_verdict_and_cli.md`` section 10.19.1, and
        ``model_evaluation_test_plan.md`` section 8.1.1.

        Returns:
            None
        """
        root = _repository_root()

        built: set[str] = set()
        for source in sorted((root / "tests").rglob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                found = _CASE_NUMBER.search(node.name)
                if found is not None and node.name.startswith("MQC_"):
                    built.add(found.group(1))

        designed: dict[str, str] = {}
        for document in sorted(root.rglob("docs/**/*.md")):
            for line in document.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                for pattern in (_PRECONDITION_ROW, _GRADED_ROW):
                    found = pattern.match(stripped)
                    if found is not None:
                        designed.setdefault(found.group(1), document.name)
                        break

        assert len(designed) > 60, (
            f"only {len(designed)} inventory rows were recognised, so a row "
            f"pattern no longer matches the inventories it is checking"
        )

        unbuilt = sorted(
            f"{number} [{document}]"
            for number, document in designed.items()
            if number not in built
        )

        assert not unbuilt, (
            f"{len(unbuilt)} inventory row(s) name a case this suite does not "
            f"implement. Implement it or record the omission with its reason; "
            f"do not remove the row: {unbuilt[:6]}"
        )


class _FakeGradedConfig:
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


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCNamedInstrument:
    """A flag that names an instrument selects it, or the record is wrong."""

    @allure.story("The named judge grades")
    def MQC_CAS_UNI_10470_the_named_judge_engine_is_the_one_that_grades(
        self,
    ) -> None:
        """``--judge-engine`` selects the engine that grades the run.

        Absent, the roster's configured judge grades. Named, that engine does,
        which is the precedence the harness resolver implements:
        ``--judge-engine``, then the roster entry, then the built-in fallback.

        **The flag reaches result metadata**, so a run whose named judge were
        ignored would record one instrument and be graded by another.

        Design: ``consumer_ci.md`` section 4.13.

        Returns:
            None
        """
        configured = judge_binding(_FakeGradedConfig(""), "gemini")
        assert configured.judge_engine == "gemini", (
            "an unnamed judge did not resolve to the configured one, so this "
            "case cannot tell an override from the default"
        )

        for named in ("openai", "claude"):
            binding = judge_binding(_FakeGradedConfig(named), "gemini")

            assert binding.judge_engine == named, (
                f"--judge-engine {named} graded with "
                f"{binding.judge_engine!r}, so the run recorded a judge that "
                f"did not produce its scores"
            )

    @allure.story("The named count is dispatched")
    def MQC_CAS_UNI_10471_the_named_observation_count_is_the_one_dispatched(
        self,
    ) -> None:
        """``--observations`` sets how many observations a case begins with.

        Absent, the roster entry's count applies. Named, that count does, and
        it is at least one so a run can never dispatch nothing.

        **An override still earns escalation.** The count is what a run begins
        with, and a single disagreement among them adds two more, so a named
        count and a configured one mean the same thing.

        Design: ``consumer_ci.md`` section 4.13.1.

        Returns:
            None
        """
        assert observation_count(_FakeGradedConfig("", observations=0)) >= 1

        for named in (1, 2, 5):
            counted = observation_count(_FakeGradedConfig("", observations=named))

            assert counted == named, (
                f"--observations {named} dispatched {counted}, so the run "
                f"measured a population it does not record"
            )

        # ESCALATION IS UNCHANGED BY AN OVERRIDE, which is what keeps a named
        # count meaning the same as a configured one.
        assert further_observations([True, False, True]) == 2
        assert further_observations([True, True, True]) == 0


def _outcome(model: str, mode: str = "live") -> Any:
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

class _FakeDispatchConfig:
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


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCRunLevelSession:
    """The session is the run's state, so it has to be the run's session."""

    @allure.story("One session serves the run")
    def MQC_CAS_UNI_10473_one_dispatch_session_serves_a_whole_run(self) -> None:
        """Every observation in a run dispatches through one session.

        The session holds the state that is only meaningful across a run: the
        spend accumulated toward ``--max-spend``, the time of the last request
        the roster's spacing is measured from, and the consecutive failures
        that open the circuit breaker. A session rebuilt per observation
        discards all three, and a ceiling on it stops nothing.

        **A different engine or ceiling is a different session**, because those
        are what define one.

        Design: ``consumer_ci.md`` section 4.15.

        Returns:
            None
        """
        config = _FakeDispatchConfig(ceiling=5.0)
        first = dispatch_session(config)

        assert dispatch_session(config) is first, (
            "a second observation built a second session, so the spend ceiling "
            "restarts at zero and can never refuse a run"
        )

        # THE SPEND ACCUMULATES, which is the whole point of the ceiling.
        first.spent = 4.99
        assert dispatch_session(config).spent == 4.99

        # AND SO DOES THE PACING STATE the spacing is measured from.
        first.last_request_at = 1234.5
        assert dispatch_session(config).last_request_at == 1234.5

        # A DIFFERENT CEILING IS A DIFFERENT SESSION, so one run's budget does
        # not silently govern another's.
        other = dispatch_session(_FakeDispatchConfig(ceiling=1.0))
        assert other is not first
        assert other.max_spend == 1.0

        # AND SO IS A DIFFERENT ENGINE, which paces on its own roster entry.
        assert dispatch_session(_FakeDispatchConfig(engine="openai")) is not first

    @allure.story("The session reports what it served")
    def MQC_CAS_UNI_10474_the_session_records_the_models_it_served(self) -> None:
        """The session records every model a response reported.

        ``reconcile`` stamps a quarantine entry with the model its
        re-observation ran against, and the resolved model reaches
        ``record_spend`` for pricing. Recording it there answers what the run
        ran against without a caller re-deriving it.

        **Two entries mean a mixed corpus**, the condition
        ``mixed_model_engines`` reports from the other direction.

        Design: ``consumer_ci.md`` section 4.15.1.

        Returns:
            None
        """
        session = DispatchSession()
        assert not session.served

        session.note_outcome(_outcome("gemini-3.8-flash"))
        session.note_outcome(_outcome("gemini-3.8-flash"))
        assert session.served == {"gemini-3.8-flash"}

        # A MIXED RUN IS VISIBLE, and an unnamed model is not recorded as one.
        session.note_outcome(_outcome("gemini-4.0-pro"))
        session.note_outcome(_outcome(""))
        assert session.served == {"gemini-3.8-flash", "gemini-4.0-pro"}

        # A REPLAY IS INCLUDED, NOT EXEMPT, which is the whole defect this
        # guards: recording on the spending hook left a replay reporting no
        # model while the fixture it replayed names one.
        replaying = DispatchSession()
        replaying.note_outcome(_outcome("gemini-3.8-flash", mode="replay"))

        assert replaying.served == {"gemini-3.8-flash"}, (
            "a replayed outcome reported no model, so the quarantine tool "
            "stamps an empty model from a replay whose fixture names one"
        )

        # AND AN OUTCOME CARRYING NO RESPONSE records nothing rather than
        # raising: a skipped case has no model to report.
        skipped = DispatchSession()
        skipped.note_outcome(
            DispatchOutcome(
                case_id="MQC_TASK_a::MQC_RULE_r", engine="gemini", mode="replay",
                duration_ms=0, duration_kind="measured", attempts=0,
                rate_limit_encounters=0, taxonomy_code="QC_HARNESS_FIXTURE_MISSING",
            )
        )
        assert not skipped.served


@allure.epic("AP-Model-QC")
@allure.feature("Consumer CI")
class TestMQCQuarantineTool:
    """Re-observing the quarantined cases, and what gets written back."""

    @allure.story("The tool writes what reconciling decided")
    def MQC_CAS_UNI_10472_the_tool_writes_what_reconciling_decided(
        self, tmp_path: Path
    ) -> None:
        """The tool re-observes each entry's case and writes the result back.

        A case that replays green loses its entry; one that was never
        observable is kept and reported undecided, which is the exit code.
        A dry run decides the same thing and writes nothing.

        **Driven in replay**, so the case contacts no provider: what is under
        test is the tool's reading, deciding and writing, not whether a model
        still fails. The live question is the operator's.

        Design: ``consumer_ci.md`` section 4.14.

        Args:
            tmp_path (Path): Standing in for ``config/``.

        Returns:
            None
        """
        folder = tmp_path / "quarantine"
        folder.mkdir()
        target = folder / "gemini.yaml"
        target.write_text(
            "quarantine:\n"
            f"  - case_id: {_REPLAYABLE_CASE}\n"
            "    reason: flaky under load\n"
            "    quarantined_on: 2026-09-01\n"
            "    observed_model: stale-model\n"
            "    ticket: MQC-7\n"
            "  - case_id: MQC_TASK_absent::MQC_RULE_absent\n"
            "    reason: never reproduced since\n"
            "    quarantined_on: 2026-09-01\n"
            "    observed_model: stale-model\n",
            encoding="utf-8",
        )
        before = target.read_text(encoding="utf-8")

        arguments = [
            "--engine", "gemini", "--mode", "replay",
            "--as-of", "2026-10-02", "--config-dir", str(tmp_path),
        ]

        # A DRY RUN DECIDES AND WRITES NOTHING, so the file is byte-identical.
        assert quarantine_tool(arguments + ["--dry-run"]) == 1
        assert target.read_text(encoding="utf-8") == before

        # AND THE REAL RUN WRITES. Exit 1 because the absent case produced no
        # observations, so its entry could not be decided.
        assert quarantine_tool(arguments) == 1

        written = load_quarantine_for(tmp_path, "gemini")
        remaining = {entry.case_id: entry for entry in written}

        assert _REPLAYABLE_CASE not in remaining, (
            "a case that replayed green kept its entry, so a finding that no "
            "longer reproduces goes on excluding"
        )

        # THE UNDECIDED ENTRY SURVIVES UNCHANGED, because a run that did not
        # ask must not extend an entry's window.
        undecided = remaining["MQC_TASK_absent::MQC_RULE_absent"]
        assert undecided.quarantined_on == date(2026, 9, 1)
        assert undecided.observed_model == "stale-model"

        # AND WHAT IT WROTE IS READABLE BY THE LOADER THAT WROTE IT, header and
        # all: a file this tool cannot read back is a file nobody can.
        assert "SPDX-License-Identifier: MIT" in target.read_text(encoding="utf-8")

    @allure.story("A stamped date is never guessed")
    def MQC_CAS_UNI_10475_the_tool_refuses_a_date_it_cannot_parse(self) -> None:
        """A date that is not ISO is refused rather than defaulted to today.

        A stamped date decides a 21-day window, so a silent default would make
        the stamp depend on when the tool happened to run.

        Design: ``consumer_ci.md`` section 4.14.

        Returns:
            None
        """
        with pytest.raises(ValueError, match="QC_HARNESS_PARSER_ERROR"):
            parse_as_of("next Tuesday")

        assert parse_as_of("2026-10-02") == date(2026, 10, 2)
