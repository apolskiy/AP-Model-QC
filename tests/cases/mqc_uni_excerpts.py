# SPDX-FileCopyrightText: 2026 Aleksandr Polskiy
# SPDX-License-Identifier: MIT
"""Preconditions guarding the code excerpts the graded cases assert against.

Covers `MQC_CAS_UNI_115100` through `115104`, inventoried in
``docs/testing/model_evaluation_test_plan.md`` section 8.

**These were harness cases until the repository split.** They read files this
repository owns, which worked only while both lived in one tree, and they failed
the moment the boundary became real. `AP-Harness-QC`, `DESIGN.md` section 5.1
records what that cost to find.

**An excerpt silently corrected by a formatter would produce a confident wrong
verdict.** Every graded case built on it would assert against an expectation
that no longer holds, and nothing would raise. That is why the guards are
preconditions rather than graded cases: a stale fixture is our defect.

A failure here is our defect, so the module carries no priority marker, per
``framework-rules.md`` section 3.3.
"""

import py_compile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_EXCERPTS = Path(__file__).resolve().parents[1] / "fixtures" / "excerpts"


def _execute_excerpt(name: str) -> dict:
    """Execute one logical-defect excerpt and return its namespace.

    **In process rather than through a subprocess.** The defect in a logical
    excerpt is what the function returns, which is a value rather than an exit
    status, so running it here asserts the defect directly instead of parsing
    printed output. It is also the only form that works identically on both
    supported platforms: capturing a subprocess under pytest fails on Windows
    with an invalid handle.

    Only the logical excerpts are executed. The syntactic one does not parse,
    which is its defect and is checked by the parser instead.

    Args:
        name (str): The excerpt file name.

    Returns:
        dict: The namespace the excerpt defined.
    """
    namespace: dict = {}
    source = (_EXCERPTS / name).read_text(encoding="utf-8")
    exec(compile(source, name, "exec"), namespace)  # pylint: disable=exec-used
    return namespace


class TestMQCCodeExcerptFixtures:
    """The excerpts still hold the defects every graded case asserts against."""

    def MQC_CAS_UNI_115100_syntactic_excerpt_still_fails_to_parse_at_recorded_line(
        self, tmp_path: Path
    ) -> None:
        """The parser is the ground truth, and it names the line.

        A model placing the error anywhere else is wrong by an exact comparison
        rather than by a rubric, which is the whole reason this formulation
        exists.

        Args:
            tmp_path (Path): pytest's temporary directory.

        Returns:
            None
        """
        source = (_EXCERPTS / "top_scorers_syntactic.py.txt").read_text(encoding="utf-8")
        staged = tmp_path / "excerpt.py"
        staged.write_text(source, encoding="utf-8")

        with pytest.raises(py_compile.PyCompileError) as caught:
            py_compile.compile(str(staged), doraise=True)

        message = str(caught.value)
        assert "was never closed" in message
        assert "line 2" in message

    def MQC_CAS_UNI_115101_logical_excerpt_still_returns_the_recorded_wrong_value(
        self,
    ) -> None:
        """This one parses, runs and raises nothing. The defect is a discarded line.

        ``sorted`` returns a new list and leaves its argument untouched, so the
        function returns the first entries in their original order. Against rows
        scoring 10, 90 and 50 it returns 10 and 90 where the correct answer is
        90 and 50.

        Returns:
            None
        """
        namespace = _execute_excerpt("top_scorers_logical.py.txt")
        entries = [{"score": 10}, {"score": 90}, {"score": 50}]
        returned = namespace["top_scorers"](entries, 2)

        assert [row["score"] for row in returned] == [10, 90]
        assert [row["score"] for row in returned] != [90, 50]

    def MQC_CAS_UNI_115102_settlement_excerpt_still_exhibits_every_recorded_defect(
        self,
    ) -> None:
        """Verification is by execution, so the finding is arithmetic.

        A hundred-unit sale at standard tier, discounted to eighty, with a
        thirty-unit coupon, should settle at fifty. It returns minus ten: the
        seller is billed ten units on a sale that should have paid fifty.

        Returns:
            None
        """
        settle_order = _execute_excerpt("settle_order_logical.py.txt")["settle_order"]

        # THE THREE REQUIRED OUTCOMES, per section 4.4.3.1. Each is produced by
        # calling the function and comparing the return against the correct
        # settlement, so every one is settled by arithmetic rather than opinion.

        # The seller pays the buyer. A hundred-unit sale discounted to eighty,
        # less a thirty-unit coupon, should settle at fifty.
        assert settle_order("standard", 100, ["SAVE30"], {"SAVE30": 30}) \
            == pytest.approx(-10.0)

        # THE GOODS ARE FREE, SILENTLY. This was absent from the guard until
        # 2026-09-23, so the outcome this family exists to catch was not itself
        # under guard. It is the one that reaches production: it raises
        # nothing, returns a number, and looks like a successful discount.
        assert settle_order("standard", 100, ["SAVE20"], {"SAVE20": 20}) \
            == pytest.approx(0.0)

        # No settlement is produced at all: the save code is undefined.
        with pytest.raises(KeyError):
            settle_order("standard", 100, ["UNKNOWN"], {"SAVE10": 30})

        # The two credited defects. Both raise on MALFORMED INPUT, where the
        # three above all involve a coupon the system accepted. Raising on bad
        # input is a robustness gap; settling a real order wrongly is a loss.
        with pytest.raises(IndexError):
            settle_order("standard", 100, [], {})
        with pytest.raises(KeyError):
            settle_order("enterprise", 100, ["SAVE10"], {"SAVE10": 30})

    def MQC_CAS_UNI_115103_the_two_top_scorer_excerpts_are_the_same_function(self) -> None:
        """Defect class is the only variable between the pair.

        That is what makes the pair worth having: without it, defect class would
        be confounded with subject matter, length or difficulty, and a
        difference in results would have three possible explanations.

        Returns:
            None
        """
        syntactic = (_EXCERPTS / "top_scorers_syntactic.py.txt").read_text(
            encoding="utf-8"
        )
        logical = (_EXCERPTS / "top_scorers_logical.py.txt").read_text(encoding="utf-8")

        assert syntactic.splitlines()[0] == logical.splitlines()[0]
        assert "def top_scorers(entries, limit):" in syntactic
        assert len(syntactic.splitlines()) < 20
        assert len(logical.splitlines()) < 20

    def MQC_CAS_UNI_115104_excerpts_are_not_collected_or_linted_as_case_code(self) -> None:
        """They carry a text suffix so no tool silently corrects them.

        A Python suffix would put them in the path of pylint, pytest collection
        and every editor's autoformatter, and a corrected excerpt leaves every
        graded case built on it asserting against an expectation that no longer
        holds.

        **This is the structural half of the guard.** Asserting their content
        without asserting their isolation would pass right up until an editor
        saved one.

        Returns:
            None
        """
        assert not list(_EXCERPTS.glob("*.py"))
        assert len(list(_EXCERPTS.glob("*.py.txt"))) == 3
