# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Whether the instrument measures the claim each case name makes.

Covers ``MQC_CAS_UNI_10461``, ``10462`` and ``10463``, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.1.

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
from pathlib import Path
from typing import Any, Final

import allure
import pytest

from evaluation.assertions import run_assertions
from cmn.vectors import is_registered_vector, match_vectors
from ingestion.schemas import GoldenRuleSet, TaskDataSet
from tests.cases.graded_support import shipped_corpus

pytestmark = pytest.mark.unit

# THIS REPOSITORY HAS TWO INVENTORY SHAPES. The precondition table carries an
# identifier, a category and a behaviour; the graded tables carry a priority and
# a condition between them. A row matching neither is a citation.
_PRECONDITION_ROW: Final[re.Pattern] = re.compile(
    r"^\|\s*`(\d{5})`\s*\|\s*[PNB]\s*\|\s*`[a-z0-9_]+`"
)
_GRADED_ROW: Final[re.Pattern] = re.compile(
    r"^\|\s*`(\d{5})`\s*\|\s*P\d\s*\|\s*`[A-Z0-9_]+`\s*\|\s*[PNB]\s*\|\s*`[a-z0-9_]+`"
)


# A security inventory row, whose fourth cell names the cases it presupposes.
_INVENTORY_ROW: Final[re.Pattern] = re.compile(r"^\|\s*`(5\d{4})`\s*\|")
_BACKTICKED_ID: Final[re.Pattern] = re.compile(r"`(\d{5})`")
_CASE_NUMBER: Final[re.Pattern] = re.compile(r"_(\d{5})_")



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
