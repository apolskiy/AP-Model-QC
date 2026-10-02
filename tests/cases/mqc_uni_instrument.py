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
from pathlib import Path
from typing import Any

import allure
import pytest

from evaluation.assertions import run_assertions
from ingestion.schemas import GoldenRuleSet, TaskDataSet
from tests.cases.graded_support import shipped_corpus

pytestmark = pytest.mark.unit


def _repository_root() -> Path:
    """Return this repository's root.

    Returns:
        Path: The directory holding ``data/``.
    """
    return Path(__file__).resolve().parents[2]


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
        """Four cases, one check, and nothing said so.

        `30003` through `30006` each dispatched `MQC_TASK_ins_quantities` with
        `MQC_RULE_ins_quantities` and called `assert_consistent_pass`. Identical
        inputs, identical assertion: **the four were indistinguishable at
        runtime**, and assertions are conjunctive, so one failing assertion
        failed all four.

        A reader opening a red `30005_sentence_begins_with_capital` would have
        investigated capitalisation. The failing assertion was
        `A_INS_COMPLETE_SENTENCE`, and capitalisation held on every observation.

        **It also corrupts the band arithmetic.** The pass floor counts cases,
        so one wrong behaviour spent four of them, and the four sat at P2, P3,
        P2 and P4, which is three bands reporting one event.

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
        """Two trailing spaces turned a complete sentence into a fragment.

        `A_INS_COMPLETE_SENTENCE` matched no bullet ending in anything but
        terminal punctuation. `gpt-4.1` wrote a bullet ending in a full stop and
        two spaces, a markdown hard line break, and the pattern matched it:
        `[ \t]*` took one space and the final class matched the other, because a
        space is not terminal punctuation.

        **It reported `QC_LLM_INSTRUCTION_DRIFT` against a compliant response**,
        on two of three observations, and was one step from being filed against
        OpenAI. `gemini-3.8-flash` never emitted a hard line break, so the
        pattern met this corpus for its whole life without the defect being
        reachable.

        **Over the recorded responses rather than synthetic text**, because the
        defect is in what a real model writes and a synthetic example would be
        written by whoever already knows the answer. Each recorded response is
        run through the shipped assertion runner twice, as recorded and with
        trailing whitespace stripped from every line. A verdict that moves means
        the assertion is measuring formatting.

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
        """Withholding content without saying why reads as a model failure.

        Section 9.12 of the test plan passes a case the provider refused and
        says the distinction is the whole of it: "a refusal is something the
        provider did, and an empty response is something that failed to
        happen." It reads `blocked_by`, which is the recorded `block_reason`.

        **Two adapters have now shipped a refusal that did not say so.** A
        gemini double of the wrong shape reported `MQC_EVL_SEC_50015` as a
        model failure for three recorded runs, and the Claude adapter mapped
        `stop_reason="refusal"` to the canonical `content_filter` while leaving
        `block_reason` empty, reporting `50013` the same way on all three
        observations.

        **This case is here rather than in the harness because the fixtures
        are here**, and because it is indifferent to which adapter wrote them.
        Both earlier defects were corrected inside one adapter, which is what
        let the second happen; a check over the recorded corpus cannot be
        satisfied one provider at a time.

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
